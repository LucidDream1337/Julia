"""Planen und Ausführen von Aufnahme-Läufen (Hintergrund-Thread, genau ein Lauf gleichzeitig)."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from . import db, embed, store
from .chunking import Block, build_chunks, content_hash, text_to_blocks
from .config import settings
from .errors import BadRequest, Conflict, JuliaError, NotFound, RobotsBlocked, RobotsUnavailable
from .webcrawl import WebCrawler, WebRules
from .wikipedia import LICENSE as WIKI_LICENSE
from .wikipedia import WikiClient

log = logging.getLogger(__name__)

_stops: dict[str, threading.Event] = {}
_start_lock = threading.Lock()
MAX_CONSECUTIVE_ERRORS = 10
MIN_WIKI_CHARS = 200


@dataclass
class Doc:
    url: str
    title: str
    blocks: list[Block]


def _cap(cfg: dict, requested: int | None) -> int:
    try:
        default = int(cfg.get("max_pages", 300))
    except (TypeError, ValueError):
        default = 300
    return max(1, min(requested or default, settings.hard_max_pages))


# --------------------------------------------------------------------------- Plan
def make_plan(kb_name: str, max_pages: int | None = None) -> dict:
    """Trockenlauf: prüft robots.txt/Erreichbarkeit und schätzt den Umfang. Lädt nichts in die Datenbank."""
    kb = db.kb_get(kb_name)
    if kb is None:
        raise NotFound(f"Wissensdatenbank '{kb_name}' gibt es nicht.")
    cfg, typ = kb["config"], kb["source_type"]
    cap = _cap(cfg, max_pages)
    plan: dict = {
        "kb": kb_name,
        "type": typ,
        "max_pages": cap,
        "notice": cfg.get("notice"),
        "license": cfg.get("license"),
        "size_hint": cfg.get("size_hint"),
    }
    if typ == "web":
        plan.update(_plan_web(cfg))
    elif typ == "wikipedia":
        plan.update(_plan_wiki(cfg, cap))
    else:
        raise BadRequest(f"Unbekannter Quelltyp: {typ}")
    delay = plan.get("delay_seconds", settings.min_delay)
    plan["estimated_minutes_max"] = round(cap * delay / 60, 1)
    plan["plan_id"] = db.plan_create(kb_name, plan)
    return plan


def _plan_web(cfg: dict) -> dict:
    rules = WebRules.from_config(cfg)
    crawler = WebCrawler(rules)
    out: dict = {"robots_ok": True, "seeds_checked": 0, "seeds_reachable": 0}
    links: list[str] = []
    problems: list[str] = []
    try:
        for seed in rules.seeds:
            out["seeds_checked"] += 1
            try:
                loaded = crawler.load(seed)
            except JuliaError as exc:
                if isinstance(exc, RobotsUnavailable):
                    out["robots_ok"] = False
                problems.append(exc.message)
                break
            if loaded.robots_blocked:
                out["robots_ok"] = False
                problems.append(f"robots.txt verbietet {seed}")
            elif loaded.page is None:
                problems.append(f"{seed}: {loaded.skip or loaded.error}")
            else:
                out["seeds_reachable"] += 1
                links.extend(l for l in loaded.page.links if l not in links)
    except RobotsUnavailable as exc:
        out["robots_ok"] = False
        problems.append(exc.message)
    finally:
        out["delay_seconds"] = crawler.fetcher.delay
        crawler.close()
    out["discovered_links"] = len(links)
    out["sample_urls"] = links[:8]
    if problems:
        out["problems"] = problems
    if not out["robots_ok"] or out["seeds_reachable"] == 0:
        out["problem"] = "; ".join(problems) or "Keine Start-URL erreichbar."
    return out


def _plan_wiki(cfg: dict, cap: int) -> dict:
    client = WikiClient(cfg)
    try:
        titles = client.resolve_titles(cfg, cap)
    finally:
        client.close()
    return {
        "language": client.lang,
        "articles": len(titles),
        "sample_titles": titles[:8],
        "delay_seconds": client.delay,
        "license": WIKI_LICENSE,
    }


# --------------------------------------------------------------------------- Start / Stopp
def start(plan_id: str, max_pages: int | None, acknowledged: bool) -> dict:
    row = db.plan_get(plan_id)
    if row is None:
        raise BadRequest("Unbekannte plan_id. Zuerst plan_ingest ausführen und das Ergebnis mit dem Nutzer besprechen.")
    if not db.plan_is_fresh(row["created_at"]):
        raise BadRequest("Der Plan ist veraltet. Bitte plan_ingest erneut ausführen.")
    plan = row["plan"]
    if plan.get("problem"):
        raise BadRequest(f"Start nicht möglich: {plan['problem']}")
    if plan.get("notice") and not acknowledged:
        raise BadRequest(
            "Bestätigung des Nutzers nötig. Lies ihm diesen Hinweis wörtlich vor, frag ausdrücklich nach "
            f"seiner Zustimmung und rufe start_ingest dann mit acknowledged=true auf: {plan['notice']}"
        )
    kb = db.kb_get(row["kb"])
    if kb is None:
        raise NotFound("Die Wissensdatenbank zum Plan existiert nicht mehr.")
    cap = max(1, min(max_pages or plan["max_pages"], settings.hard_max_pages))
    with _start_lock:
        running = db.job_running()
        if running:
            raise Conflict(
                f"Es läuft bereits ein Job ({running['id']} für '{running['kb']}'). "
                "Warte, bis er fertig ist, oder stoppe ihn mit stop_job."
            )
        job_id = db.job_create(kb["name"], cap)
        _stops[job_id] = threading.Event()
        threading.Thread(target=_run, args=(job_id, kb, cap), name=f"job-{job_id}", daemon=True).start()
    return db.job_get(job_id)


def stop(job_id: str) -> dict:
    job = db.job_get(job_id)
    if job is None:
        raise NotFound(f"Job '{job_id}' gibt es nicht.")
    event = _stops.get(job_id)
    if event is not None:
        event.set()
    return job


# --------------------------------------------------------------------------- Lauf
def _documents(kb: dict, cap: int, stop_event: threading.Event, stats: dict, save):
    """Liefert Doc-Objekte; zählt Fehler/Übersprungenes in stats."""
    cfg, typ = kb["config"], kb["source_type"]
    consecutive = 0
    if typ == "web":
        crawler = WebCrawler(WebRules.from_config(cfg))
        try:
            for loaded in crawler.crawl(cap, stop_event.is_set):
                stats["current"] = loaded.url
                if loaded.page is None:
                    if loaded.error:
                        stats["errors"] += 1
                        stats["last_error"] = f"{loaded.url}: {loaded.error}"
                        consecutive += 1
                        if consecutive >= MAX_CONSECUTIVE_ERRORS:
                            raise JuliaError(f"Abbruch nach {consecutive} Fehlern in Folge. Letzter: {stats['last_error']}")
                    else:
                        stats["skipped"] += 1
                    save()
                    continue
                consecutive = 0
                yield Doc(loaded.page.url, loaded.page.title, loaded.page.blocks)
        finally:
            crawler.close()
    else:
        client = WikiClient(cfg)
        try:
            titles = client.resolve_titles(cfg, cap)
            for title in titles:
                if stop_event.is_set():
                    return
                stats["current"] = title
                try:
                    page = client.extract(title)
                except JuliaError:
                    raise
                except Exception as exc:
                    stats["errors"] += 1
                    stats["last_error"] = f"{title}: {exc}"
                    consecutive += 1
                    if consecutive >= MAX_CONSECUTIVE_ERRORS:
                        raise JuliaError(f"Abbruch nach {consecutive} Fehlern in Folge. Letzter: {stats['last_error']}")
                    continue
                consecutive = 0
                if page is None or len(page.text) < MIN_WIKI_CHARS:
                    stats["skipped"] += 1
                    save()
                    continue
                yield Doc(page.url, page.title, text_to_blocks(page.text))
        finally:
            client.close()


def _index(kb: dict, doc: Doc, stats: dict, state: dict) -> None:
    name, cfg = kb["name"], kb["config"]
    chunks = build_chunks(doc.blocks, settings.chunk_max_chars, settings.chunk_min_chars)
    if not chunks:
        stats["skipped"] += 1
        return
    digest = content_hash(doc.title, chunks)
    if db.page_hash(name, doc.url) == digest:
        stats["unchanged"] += 1
        return
    inputs = [f"{doc.title} - {c.section}\n{c.text}" if c.section else f"{doc.title}\n{c.text}" for c in chunks]
    vectors = embed.get().embed_documents(inputs)
    if not state.get("ready"):
        store.ensure(kb["collection"], len(vectors[0]))
        state["ready"] = True
    fetched = db.now()
    source = cfg.get("preset") or kb["source_type"]
    points = [
        store.make_point(doc.url, i, vec, {
            "kb": name, "url": doc.url, "title": doc.title, "section": c.section, "text": c.text,
            "source": source, "license": cfg.get("license", ""),
            "lang": cfg.get("language") or cfg.get("lang", ""), "fetched_at": fetched,
        })
        for i, (c, vec) in enumerate(zip(chunks, vectors))
    ]
    store.replace_page(kb["collection"], doc.url, points)
    db.page_put(name, doc.url, digest, len(chunks), doc.title)
    stats["pages"] += 1
    stats["chunks"] += len(chunks)


def _run(job_id: str, kb: dict, cap: int) -> None:
    stats = {"pages": 0, "chunks": 0, "unchanged": 0, "skipped": 0, "errors": 0, "current": "", "last_error": ""}
    stop_event = _stops[job_id]
    state: dict = {}

    def save(status: str | None = None, message: str | None = None) -> None:
        db.job_update(job_id, status=status, message=message, stats=stats)

    try:
        save()
        for doc in _documents(kb, cap, stop_event, stats, save):
            try:
                _index(kb, doc, stats, state)
            except JuliaError:
                raise
            except Exception as exc:  # einzelne Seite kaputt: weiter mit der nächsten
                stats["errors"] += 1
                stats["last_error"] = f"{doc.url}: {exc}"
                log.warning("Seite übersprungen: %s", stats["last_error"])
            save()
            if stop_event.is_set():
                break
        if stop_event.is_set():
            save("stopped", "Vom Nutzer gestoppt. Bisher Gelerntes bleibt erhalten.")
        else:
            save("done", f"Fertig: {stats['pages']} neue/geänderte Seiten, {stats['chunks']} Abschnitte.")
    except RobotsBlocked as exc:
        save("failed", exc.message)
    except JuliaError as exc:
        save("failed", exc.message)
    except Exception as exc:  # letzte Absicherung, damit der Job nie "running" hängen bleibt
        log.exception("Job %s abgestürzt", job_id)
        save("failed", f"Unerwarteter Fehler: {exc}")
    finally:
        _stops.pop(job_id, None)
