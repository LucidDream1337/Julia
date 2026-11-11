"""FastAPI-Anwendung.

Öffentlich im OpenAPI-Schema (für Open WebUI als Tool): /ask und /health.
Verborgen und per X-Admin-Token geschützt: /crawl, /learn, /status – damit das
Sprachmodell Crawls niemals von sich aus auslösen kann.
"""
from __future__ import annotations

import hmac
import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import __version__, llm, rag
from .config import settings, setup_logging
from .errors import OllamaError, StoreError
from .learning import RunLock, execute_run, read_status
from .store import Store

setup_logging()
log = logging.getLogger("agent.api")

app = FastAPI(
    title="Programming Learning Agent",
    version=__version__,
    description=(
        "Lokale Wissensdatenbank mit Programmier-Lernmaterial (W3Schools) für RAG. "
        "Nutze /ask, um Programmierfragen mit Quellenangabe zu beantworten."
    ),
)


# -- Modelle --------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(
        ..., min_length=3, max_length=2000,
        description="Die Programmierfrage des Lernenden, z. B. 'Wie funktionieren Listen in Python?'",
    )
    top_k: int = Field(
        default=settings.top_k, ge=1, le=10,
        description="Wie viele Lernmaterial-Auszüge berücksichtigt werden.",
    )
    generate: bool = Field(
        default=True,
        description="true: fertige Antwort mit Quellen. false: nur die gefundenen Auszüge liefern.",
    )


class SourceInfo(BaseModel):
    number: int
    title: str
    section: str = ""
    url: str
    score: float
    excerpt: str = Field(default="", description="Nur bei generate=false gefüllt.")


class AskResponse(BaseModel):
    question: str
    search_query: str
    answer: Optional[str] = None
    sources: list[SourceInfo]
    knowledge_found: bool


class LearnRequest(BaseModel):
    max_pages: Optional[int] = Field(default=None, ge=1, le=200)


class CrawlRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=50)


# -- Öffentliche Endpunkte (Tool-Schnittstelle) ------------------------------------
@app.post(
    "/ask",
    response_model=AskResponse,
    operation_id="ask_programming_question",
    summary="Programmierfrage mit Lernmaterial beantworten",
    description=(
        "Durchsucht die lokale Wissensdatenbank (W3Schools-Lernmaterial) und beantwortet die "
        "Frage auf Basis der gefundenen Auszüge, inklusive Quellen-URLs. Verwende dieses Tool "
        "bei jeder Frage zu Programmiersprachen, Syntax, HTML, CSS, SQL oder JavaScript."
    ),
)
def ask_endpoint(req: AskRequest) -> AskResponse:
    try:
        result = rag.ask(req.question, top_k=req.top_k, generate=req.generate)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except StoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return AskResponse(**result)


@app.get(
    "/health",
    operation_id="health_check",
    summary="Status von Agent, Ollama und Wissensdatenbank",
)
def health() -> dict:
    checks: dict = {}
    ok = True

    try:
        installed = llm.list_models()
        llm_ok = llm.model_available(settings.ollama_model, installed)
        emb_ok = llm.model_available(settings.ollama_embedding_model, installed)
        checks["ollama"] = {
            "reachable": True,
            "llm_model": settings.ollama_model,
            "llm_model_available": llm_ok,
            "embedding_model": settings.ollama_embedding_model,
            "embedding_model_available": emb_ok,
        }
        ok = ok and llm_ok and emb_ok
    except OllamaError as exc:
        checks["ollama"] = {"reachable": False, "error": str(exc)}
        ok = False

    try:
        store = Store()
        checks["qdrant"] = {
            "reachable": True,
            "collection": settings.collection_name,
            "collection_exists": store.exists(),
            "chunks": store.count(),
        }
    except StoreError as exc:
        checks["qdrant"] = {"reachable": False, "error": str(exc)}
        ok = False

    return {"status": "ok" if ok else "degraded", "version": __version__, "checks": checks}


# -- Verborgene Admin-Endpunkte ------------------------------------------------------
def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not settings.admin_token:
        raise HTTPException(503, "ADMIN_TOKEN ist nicht gesetzt – Admin-API deaktiviert.")
    if not hmac.compare_digest(x_admin_token.encode(), settings.admin_token.encode()):
        raise HTTPException(401, "Ungültiges Admin-Token.")


admin = APIRouter(dependencies=[Depends(require_admin)])


def _start_background(max_pages: Optional[int], urls: Optional[list[str]], trigger: str) -> None:
    lock = RunLock()
    if not lock.acquire():
        raise HTTPException(409, "Es läuft bereits ein Lernlauf.")

    def target() -> None:
        try:
            execute_run(max_pages=max_pages, urls=urls, trigger=trigger)
        except Exception:
            log.exception("Hintergrund-Lernlauf fehlgeschlagen")
        finally:
            lock.release()

    threading.Thread(target=target, name="learning-run", daemon=True).start()


@admin.post("/learn", status_code=202)
def learn(req: LearnRequest | None = None) -> dict:
    """Startet einen regulären Lernlauf (nächste Seiten aus der Warteschlange)."""
    _start_background((req.max_pages if req else None), None, "api-learn")
    return {"accepted": True, "detail": "Lernlauf gestartet. Fortschritt: GET /status"}


@admin.post("/crawl", status_code=202)
def crawl(req: CrawlRequest) -> dict:
    """Lädt und indexiert gezielt die angegebenen (erlaubten) URLs neu."""
    _start_background(None, req.urls, "api-crawl")
    return {"accepted": True, "detail": "Crawl gestartet. Fortschritt: GET /status"}


@admin.get("/status")
def status() -> dict:
    return read_status()


app.include_router(admin, include_in_schema=False)
