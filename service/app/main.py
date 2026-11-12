"""HTTP-API (OpenAPI) für Open WebUI. Jede Route ist ein Werkzeug (Tool) für Julia."""
import logging
import re
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import db, embed, jobs, presets, store
from .config import settings
from .errors import BadRequest, JuliaError, NotFound

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("julia")

@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    log.info("Julia-Service gestartet (Embedding-Modell %s)", settings.embed_model)
    yield


app = FastAPI(
    title="Julia Wissen",
    version="1.0",
    lifespan=lifespan,
    description=(
        "Werkzeuge für Julia: Wissensdatenbanken anlegen, aus Webseiten/Wikipedia befüllen, "
        "durchsuchen, und Skills (Arbeitsanleitungen) lesen."
    ),
)


@app.exception_handler(JuliaError)
async def _julia_error(_: Request, exc: JuliaError):
    return JSONResponse(status_code=exc.status, content={"error": exc.message})


# --------------------------------------------------------------------------- Modelle
class CreateKB(BaseModel):
    name: str = Field(description="Kurzer Name, nur Kleinbuchstaben/Ziffern/-/_ (z. B. 'w3schools-python').")
    description: str = Field("", description="Ein Satz: Wofür ist diese Wissensdatenbank?")
    preset: str | None = Field(None, description="Name einer Vorlage aus list_presets, z. B. 'w3schools'.")
    parts: list[str] | None = Field(None, description="Teilbereiche der Vorlage (z. B. ['python','sql']). Leer = alle.")
    type: str | None = Field(None, description="Nur ohne Preset: 'web' oder 'wikipedia'.")
    config: dict | None = Field(None, description="Quellen-Konfiguration bzw. Überschreibungen der Vorlage.")


class PlanReq(BaseModel):
    max_pages: int | None = Field(None, ge=1, description="Obergrenze für Seiten/Artikel dieses Laufs.")


class IngestReq(BaseModel):
    plan_id: str = Field(description="plan_id aus plan_ingest.")
    max_pages: int | None = Field(None, ge=1, description="Optional kleinere Obergrenze (z. B. 10 für einen Probelauf).")
    acknowledged: bool = Field(False, description="true NUR, wenn der Nutzer den Hinweis aus dem Plan ausdrücklich bestätigt hat.")


class SearchReq(BaseModel):
    query: str = Field(description="Suchbegriff bzw. Frage. Bei englischen Quellen am besten auf Englisch formulieren.")
    kb: str | None = Field(None, description="Name einer Wissensdatenbank. Leer = in allen suchen.")
    top_k: int = Field(5, ge=1, le=10)


# --------------------------------------------------------------------------- System
@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}


@app.get("/status", operation_id="service_status", summary="Diagnose: sind Ollama, Qdrant und Einstellungen in Ordnung?")
def service_status():
    """Prüft Erreichbarkeit von Ollama/Qdrant und ob das Embedding-Modell installiert ist. Bei Problemen zuerst aufrufen."""
    out: dict = {"embedding_model": settings.embed_model, "crawler_contact_set": bool(settings.contact)}
    try:
        resp = httpx.get(f"{settings.ollama_url}/api/tags", timeout=10)
        resp.raise_for_status()
        names = [m.get("name", "").lower() for m in resp.json().get("models", [])]
        wanted = settings.embed_model.lower()
        out["ollama"] = "ok"
        out["embedding_model_installed"] = any(n == wanted or n.startswith(wanted + ":") for n in names)
    except Exception as exc:
        out["ollama"] = f"Fehler: {exc}"
    try:
        store.client().get_collections()
        out["qdrant"] = "ok"
    except Exception as exc:
        out["qdrant"] = f"Fehler: {exc}"
    return out


# --------------------------------------------------------------------------- Skills
_SKILL_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")


def _skill_files():
    if not settings.skills_dir.is_dir():
        return []
    return sorted(settings.skills_dir.glob("*.md"))


@app.get("/skills", operation_id="list_skills", summary="Verfügbare Skills (Arbeitsanleitungen) auflisten")
def list_skills():
    """Skills sind kurze Rezepte für wiederkehrende Aufgaben. Vor einer passenden Aufgabe mit read_skill laden."""
    out = []
    for path in _skill_files():
        lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        title = lines[0].lstrip("# ").strip() if lines else path.stem
        out.append({"name": path.stem, "title": title, "description": lines[1] if len(lines) > 1 else ""})
    return {"skills": out}


@app.get("/skills/{name}", operation_id="read_skill", summary="Ein Skill vollständig lesen und befolgen")
def read_skill(name: str):
    """Liefert den Text des Skills. Halte dich Schritt für Schritt daran."""
    if not _SKILL_RE.match(name):
        raise BadRequest("Ungültiger Skill-Name.")
    path = settings.skills_dir / f"{name}.md"
    if not path.is_file():
        raise NotFound(f"Skill '{name}' gibt es nicht. Verfügbare Skills mit list_skills abrufen.")
    return {"name": name, "content": path.read_text(encoding="utf-8")}


# --------------------------------------------------------------------------- Wissensdatenbanken
@app.get("/presets", operation_id="list_presets", summary="Quellen-Vorlagen (W3Schools, Wikipedia, Pflanzenatlas, ...) auflisten")
def list_presets():
    """Zeigt fertige Vorlagen mit Teilbereichen (parts) und ob eine Bestätigung des Nutzers nötig ist."""
    return {"presets": presets.list_presets()}


@app.get("/knowledge", operation_id="list_knowledge_bases", summary="Vorhandene Wissensdatenbanken mit Stand auflisten")
def list_knowledge_bases():
    """Name, Beschreibung, Anzahl gelernter Seiten/Abschnitte und letzter Job je Wissensdatenbank."""
    out = []
    for kb in db.kb_list():
        pages, chunks = db.page_stats(kb["name"])
        last = db.job_list(kb["name"], 1)
        out.append({
            "name": kb["name"],
            "description": kb["description"],
            "preset": kb["preset"],
            "type": kb["source_type"],
            "pages": pages,
            "chunks": chunks,
            "last_job": ({"id": last[0]["id"], "status": last[0]["status"], "message": last[0]["message"]} if last else None),
        })
    return {"knowledge_bases": out}


@app.post("/knowledge", operation_id="create_knowledge_base", summary="Neue (leere) Wissensdatenbank anlegen")
def create_knowledge_base(req: CreateKB):
    """Legt die Wissensdatenbank samt Quellen-Konfiguration an. Es wird noch nichts heruntergeladen (dafür plan_ingest, dann start_ingest)."""
    name = presets.validate_name(req.name)
    if db.kb_get(name):
        raise BadRequest(f"Eine Wissensdatenbank '{name}' gibt es schon.")
    typ, cfg = presets.build_config(req.preset, req.parts, req.type, req.config)
    db.kb_create(name, req.description.strip(), store.collection_name(name), req.preset, typ, cfg)
    return {"created": name, "type": typ, "next": "plan_ingest ausführen und den Plan mit dem Nutzer besprechen."}


@app.delete("/knowledge/{name}", operation_id="delete_knowledge_base", summary="Wissensdatenbank samt Inhalt löschen")
def delete_knowledge_base(name: str, confirm: str = ""):
    """UNWIDERRUFLICH. Nur nach ausdrücklichem Wunsch des Nutzers; confirm muss exakt dem Namen entsprechen."""
    kb = db.kb_get(name)
    if kb is None:
        raise NotFound(f"Wissensdatenbank '{name}' gibt es nicht.")
    if confirm != name:
        raise BadRequest(f"Zum Löschen confirm='{name}' angeben, nachdem der Nutzer das ausdrücklich bestätigt hat.")
    running = db.job_running()
    if running and running["kb"] == name:
        raise BadRequest("Für diese Wissensdatenbank läuft gerade ein Job. Erst stop_job.")
    store.delete_collection(kb["collection"])
    db.kb_delete(name)
    return {"deleted": name}


# --------------------------------------------------------------------------- Aufnahme
@app.post("/knowledge/{name}/plan", operation_id="plan_ingest", summary="Trockenlauf: Umfang, robots.txt und Dauer prüfen (lädt nichts)")
def plan_ingest(name: str, req: PlanReq):
    """Prüft Erreichbarkeit und robots.txt und schätzt Seitenzahl und Dauer. Ergebnis dem Nutzer erklären, dann auf sein Ja warten."""
    return jobs.make_plan(name, req.max_pages)


@app.post("/ingest", operation_id="start_ingest", summary="Befüllen starten (nur nach plan_ingest UND Ja des Nutzers)")
def start_ingest(req: IngestReq):
    """Startet den Hintergrundlauf. Den Fortschritt mit job_status abfragen."""
    job = jobs.start(req.plan_id, req.max_pages, req.acknowledged)
    return {"job": job, "next": "Mit job_status den Fortschritt abfragen."}


@app.get("/jobs", operation_id="list_jobs", summary="Letzte Jobs auflisten")
def list_jobs(kb: str | None = None):
    return {"jobs": db.job_list(kb, 5)}


@app.get("/jobs/{job_id}", operation_id="job_status", summary="Fortschritt eines Jobs abfragen")
def job_status(job_id: str):
    """Status (running/done/stopped/failed/interrupted), Zähler und aktuelle Seite."""
    job = db.job_get(job_id)
    if job is None:
        raise NotFound(f"Job '{job_id}' gibt es nicht.")
    return job


@app.post("/jobs/{job_id}/stop", operation_id="stop_job", summary="Laufenden Job sauber stoppen")
def stop_job(job_id: str):
    """Der Job beendet die aktuelle Seite und hält an. Bereits Gelerntes bleibt erhalten."""
    return {"job": jobs.stop(job_id), "note": "Stopp angefordert; Status in einigen Sekunden mit job_status prüfen."}


# --------------------------------------------------------------------------- Suche
@app.post("/search", operation_id="search_knowledge", summary="In den Wissensdatenbanken suchen")
def search_knowledge(req: SearchReq):
    """Liefert die passendsten Textauszüge mit Quelle (url). Antworte nur anhand der Treffer und nenne die Quelle."""
    targets = [db.kb_get(req.kb)] if req.kb else db.kb_list()
    if req.kb and targets[0] is None:
        raise NotFound(f"Wissensdatenbank '{req.kb}' gibt es nicht. Vorhandene mit list_knowledge_bases abrufen.")
    if not targets:
        return {"results": [], "hint": "Es gibt noch keine Wissensdatenbank. Biete an, eine anzulegen."}
    vector = embed.get().embed_query(req.query)
    hits: list[dict] = []
    for kb in targets:
        hits.extend(store.search(kb["collection"], vector, req.top_k, settings.search_min_score))
    hits.sort(key=lambda h: -h["score"])
    hits = hits[: req.top_k]
    if not hits:
        return {"results": [], "hint": "Keine passenden Treffer. Sag das offen; formuliere ggf. den Suchbegriff um (Sprache der Quelle) oder nutze die Websuche."}
    return {
        "results": [
            {"kb": h.get("kb"), "title": h.get("title"), "section": h.get("section"), "url": h.get("url"),
             "score": round(h["score"], 3), "text": h.get("text")}
            for h in hits
        ],
        "hint": "Antworte nur anhand dieser Auszüge, nenne die Quelle (url) und erfinde nichts dazu.",
    }
