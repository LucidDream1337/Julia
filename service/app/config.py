"""Konfiguration ausschließlich über Umgebungsvariablen (siehe .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

USER_AGENT_TOKEN = "JuliaBot"


def _int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(minimum, value)


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError:
        value = default
    return max(minimum, value)


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    embed_model: str
    qdrant_url: str
    data_dir: Path
    skills_dir: Path
    presets_dir: Path
    contact: str
    chunk_max_chars: int
    chunk_min_chars: int
    hard_max_pages: int
    min_delay: float
    search_min_score: float
    plan_ttl_hours: int
    log_level: str

    @property
    def user_agent(self) -> str:
        who = self.contact or "kontakt-nicht-gesetzt"
        return f"{USER_AGENT_TOKEN}/1.0 (private Wissensdatenbank; Kontakt: {who})"


def load_settings() -> Settings:
    return Settings(
        ollama_url=os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/"),
        embed_model=os.environ.get("EMBED_MODEL", "bge-m3").strip(),
        qdrant_url=os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/"),
        data_dir=Path(os.environ.get("DATA_DIR", "/data")),
        skills_dir=Path(os.environ.get("SKILLS_DIR", "/skills")),
        presets_dir=Path(os.environ.get("PRESETS_DIR", "/presets")),
        contact=os.environ.get("CRAWLER_CONTACT", "").strip(),
        chunk_max_chars=_int("CHUNK_MAX_CHARS", 1200, 400),
        chunk_min_chars=_int("CHUNK_MIN_CHARS", 300, 100),
        hard_max_pages=_int("HARD_MAX_PAGES", 5000),
        # Untergrenze der Pause zwischen zwei Anfragen an denselben Server.
        min_delay=_float("MIN_CRAWL_DELAY", 2.0, 1.0),
        search_min_score=_float("SEARCH_MIN_SCORE", 0.35),
        plan_ttl_hours=_int("PLAN_TTL_HOURS", 24),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    )


settings = load_settings()
