"""Lernlauf: Frontier abarbeiten -> robots.txt prüfen -> laden -> parsen -> chunken ->
Embeddings -> Qdrant. Wird von API (/learn, /crawl), Worker und CLI gemeinsam genutzt."""
from __future__ import annotations

import fcntl
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from qdrant_client.http import models as qm

from .config import settings
from .crawler import (
    SOURCES, Fetcher, ParseError, RobotsGuard, build_chunks, content_hash,
    normalize_url, parse_page, source_for_url,
)
from .db import StateDB
from .embeddings import OllamaEmbedder
from .errors import CrawlAbort, OllamaError, RobotsUnavailable, StoreError
from .store import Store, point_id

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- Sperre: verhindert parallele Läufe (API-Container und Worker-Container) -----
class RunLock:
    def __init__(self) -> None:
        self._fd: int | None = None

    def acquire(self) -> bool:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(settings.lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def release(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    @staticmethod
    def is_locked() -> bool:
        probe = RunLock()
        if probe.acquire():
            probe.release()
            return False
        return True


# -- Status-Datei -------------------------------------------------------------
def write_status(data: dict[str, Any]) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    tmp = settings.status_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(settings.status_path)


def read_status() -> dict[str, Any]:
    try:
        status = json.loads(settings.status_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        status = {"state": "never_run"}
    if status.get("state") == "running" and not RunLock.is_locked():
        status["state"] = "interrupted"  # Container wurde während des Laufs beendet
    return status


# -- Kern ---------------------------------------------------------------------
class _Context:
    def __init__(self) -> None:
        self.db = StateDB(settings.state_db_path)
        self.fetcher = Fetcher()
        self.robots = RobotsGuard(self.fetcher)
        self.store = Store()
        self.embedder = OllamaEmbedder()

    def close(self) -> None:
        self.fetcher.close()
        self.embedder.close()
        self.db.close()


def _process_page(ctx: _Context, url: str, force: bool) -> str:
    source = source_for_url(url)
    if source is None or not source.accepts(url):
        ctx.db.mark_status(url, "skipped", "URL nicht durch Quellen-Konfiguration erlaubt")
        return "skipped"

    if not ctx.robots.can_fetch(url):  # kann RobotsUnavailable werfen -> Abbruch
        ctx.store.delete_page(url)
        ctx.db.mark_status(url, "blocked", "durch robots.txt gesperrt")
        log.info("robots.txt sperrt %s", url)
        return "blocked"

    try:
        resp = ctx.fetcher.get(url)
    except httpx.HTTPError as exc:
        ctx.db.mark_error(url, f"Netzwerkfehler: {exc}")
        return "error"

    if resp.status_code in (404, 410):
        ctx.store.delete_page(url)
        ctx.db.mark_status(url, "gone", f"HTTP {resp.status_code}")
        return "gone"
    if resp.status_code == 429 or resp.status_code == 503:
        raise CrawlAbort(f"Server bremst (HTTP {resp.status_code}) – Lauf wird abgebrochen.")
    if resp.status_code != 200:
        ctx.db.mark_error(url, f"HTTP {resp.status_code}")
        return "error"

    final_url = normalize_url(str(resp.url), url) or url
    if not source.accepts(final_url):
        ctx.db.mark_status(url, "skipped", f"Weiterleitung auf nicht erlaubte URL: {final_url}")
        return "skipped"
    if "html" not in resp.headers.get("content-type", "").lower():
        ctx.db.mark_status(url, "skipped", "kein HTML")
        return "skipped"

    try:
        parsed = parse_page(resp.text, final_url, source)
    except ParseError as exc:
        ctx.db.mark_error(url, str(exc))
        return "error"

    ctx.db.add_urls(source.name, parsed.links)

    chunks = build_chunks(parsed.blocks, settings.chunk_max_chars, settings.chunk_min_chars)
    if not chunks:
        ctx.db.mark_error(url, "kein extrahierbarer Inhalt")
        return "error"

    new_hash = content_hash(parsed.title, chunks)
    previous = ctx.db.get(url)
    if (
        not force
        and previous is not None
        and previous["status"] == "ok"
        and previous["content_hash"] == new_hash
    ):
        ctx.db.touch_ok(url)
        return "unchanged"

    texts = [
        f"{parsed.title} – {c.section}\n{c.text}" if c.section and c.section != parsed.title
        else f"{parsed.title}\n{c.text}"
        for c in chunks
    ]
    vectors = ctx.embedder.embed_documents(texts)
    crawled_at = _now_iso()
    points = [
        qm.PointStruct(
            id=point_id(url, i),
            vector=vec,
            payload={
                "url": url,
                "title": parsed.title,
                "section": chunk.section,
                "topic": parsed.topic,
                "source": source.name,
                "chunk_index": i,
                "text": chunk.text,
                "content_hash": new_hash,
                "crawled_at": crawled_at,
            },
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]
    ctx.store.replace_page(url, points)
    ctx.db.mark_ok(url, parsed.title, new_hash, len(chunks))
    log.info("Indexiert: %s (%d Chunks)", url, len(chunks))
    return "indexed"


def execute_run(
    max_pages: int | None = None,
    urls: list[str] | None = None,
    trigger: str = "manual",
) -> dict[str, Any]:
    """Führt einen Lernlauf aus. Der Aufrufer MUSS vorher die RunLock halten."""
    limit = max_pages or settings.max_pages_per_run
    summary: dict[str, Any] = {
        "state": "running",
        "trigger": trigger,
        "mode": "urls" if urls else "frontier",
        "started_at": _now_iso(),
        "finished_at": None,
        "max_pages": limit,
        "counts": {k: 0 for k in ("indexed", "unchanged", "blocked", "gone", "error", "skipped")},
        "aborted_reason": None,
        "rejected_urls": [],
    }
    write_status(summary)
    log.info("Lernlauf gestartet (%s, Modus=%s, max=%d)", trigger, summary["mode"], limit)

    ctx = _Context()
    try:
        # Dimension aus dem ersten echten Embedding ermitteln, Collection danach anlegen.
        probe = ctx.embedder.embed_documents(["dimension probe"])
        ctx.store.ensure_collection(len(probe[0]))

        for source in SOURCES:
            ctx.db.add_urls(source.name, list(source.seeds))

        force = False
        if urls:
            force = True
            targets: list[str] = []
            for raw in urls[:limit]:
                url = normalize_url(raw, "https://invalid.example/")
                src = source_for_url(url) if url else None
                if not url or src is None or not src.accepts(url):
                    summary["rejected_urls"].append(raw)
                    continue
                ctx.db.add_urls(src.name, [url])
                targets.append(url)
        else:
            targets = ctx.db.next_batch(limit, settings.recrawl_after_days)

        for url in targets:
            try:
                outcome = _process_page(ctx, url, force)
            except (OllamaError, StoreError, RobotsUnavailable, CrawlAbort):
                raise
            except Exception as exc:  # unerwarteter Fehler auf EINER Seite stoppt nicht alles
                log.exception("Unerwarteter Fehler bei %s", url)
                ctx.db.mark_error(url, f"{type(exc).__name__}: {exc}")
                outcome = "error"
            summary["counts"][outcome] += 1
        summary["state"] = "finished"
    except (OllamaError, StoreError, RobotsUnavailable, CrawlAbort) as exc:
        log.error("Lernlauf abgebrochen: %s", exc)
        summary["state"] = "aborted"
        summary["aborted_reason"] = str(exc)
    except Exception as exc:
        log.exception("Lernlauf mit unerwartetem Fehler beendet")
        summary["state"] = "failed"
        summary["aborted_reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            summary["knowledge_base"] = ctx.db.stats()
        except Exception:
            pass
        ctx.close()
        summary["finished_at"] = _now_iso()
        write_status(summary)

    log.info("Lernlauf beendet: %s %s", summary["state"], summary["counts"])
    return summary
