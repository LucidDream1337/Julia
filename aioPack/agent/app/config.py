"""Zentrale Konfiguration. Alles ist per Umgebungsvariable überschreibbar."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


def _str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or not value.strip() else value.strip()


def _int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw.strip()) if raw and raw.strip() else default
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _float(name: str, default: float, minimum: float | None = None) -> float:
    raw = os.getenv(name)
    try:
        value = float(raw.strip()) if raw and raw.strip() else default
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "ja"}


@dataclass(frozen=True)
class Settings:
    # Ollama
    ollama_base_url: str
    ollama_model: str
    ollama_embedding_model: str
    ollama_num_ctx: int
    ollama_timeout: float
    # Qdrant
    qdrant_url: str
    qdrant_api_key: str
    collection_name: str
    # Daten / Crawler
    data_dir: Path
    crawl_delay_seconds: float
    max_pages_per_run: int
    crawl_interval_hours: float
    recrawl_after_days: int
    user_agent: str
    chunk_max_chars: int
    chunk_min_chars: int
    # RAG
    top_k: int
    min_score: float
    max_context_chars: int
    query_rewrite: bool
    # Betrieb
    admin_token: str
    worker_initial_delay_seconds: int
    log_level: str

    @property
    def state_db_path(self) -> Path:
        return self.data_dir / "state.db"

    @property
    def lock_path(self) -> Path:
        return self.data_dir / "learn.lock"

    @property
    def status_path(self) -> Path:
        return self.data_dir / "status.json"


# Produkt-Token für robots.txt-Auswertung (ohne Leerzeichen/Versionsnummer).
USER_AGENT_TOKEN = "ProgrammingSchoolLearningBot"


def load_settings() -> Settings:
    return Settings(
        ollama_base_url=_str("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/"),
        ollama_model=_str("OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_embedding_model=_str("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        ollama_num_ctx=_int("OLLAMA_NUM_CTX", 8192, minimum=1024),
        ollama_timeout=_float("OLLAMA_TIMEOUT_SECONDS", 300.0, minimum=10.0),
        qdrant_url=_str("QDRANT_URL", "http://qdrant:6333").rstrip("/"),
        qdrant_api_key=_str("QDRANT_API_KEY", ""),
        collection_name=_str("COLLECTION_NAME", "programming_knowledge"),
        data_dir=Path(_str("DATA_DIR", "/data")),
        # Mindestens 2 Sekunden Pause – niedrigere Werte werden ignoriert.
        crawl_delay_seconds=_float("CRAWL_DELAY_SECONDS", 2.0, minimum=2.0),
        max_pages_per_run=_int("MAX_PAGES_PER_RUN", 25, minimum=1, maximum=500),
        crawl_interval_hours=_float("CRAWL_INTERVAL_HOURS", 24.0, minimum=0.5),
        recrawl_after_days=_int("RECRAWL_AFTER_DAYS", 30, minimum=1),
        user_agent=_str(
            "CRAWLER_USER_AGENT",
            f"{USER_AGENT_TOKEN}/1.0 (privates Lernprojekt; respektiert robots.txt)",
        ),
        chunk_max_chars=_int("CHUNK_MAX_CHARS", 1200, minimum=400),
        chunk_min_chars=_int("CHUNK_MIN_CHARS", 300, minimum=100),
        top_k=_int("RAG_TOP_K", 4, minimum=1, maximum=10),
        min_score=_float("RAG_MIN_SCORE", 0.35),
        max_context_chars=_int("RAG_MAX_CONTEXT_CHARS", 6000, minimum=1000),
        query_rewrite=_bool("RAG_QUERY_REWRITE", True),
        admin_token=_str("ADMIN_TOKEN", ""),
        worker_initial_delay_seconds=_int("WORKER_INITIAL_DELAY_SECONDS", 60, minimum=0),
        log_level=_str("LOG_LEVEL", "INFO").upper(),
    )


settings = load_settings()


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # httpx loggt jede Anfrage auf INFO – das wäre sehr laut.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
