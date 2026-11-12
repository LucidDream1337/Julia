"""SQLite-Zustand: Wissensdatenbanken, Seiten-Hashes, Pläne und Jobs."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .config import settings

_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS kbs (
    name        TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    collection  TEXT NOT NULL,
    preset      TEXT,
    source_type TEXT NOT NULL,
    config      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
    kb         TEXT NOT NULL,
    url        TEXT NOT NULL,
    hash       TEXT NOT NULL,
    chunks     INTEGER NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (kb, url)
);
CREATE TABLE IF NOT EXISTS plans (
    id         TEXT PRIMARY KEY,
    kb         TEXT NOT NULL,
    plan       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id         TEXT PRIMARY KEY,
    kb         TEXT NOT NULL,
    status     TEXT NOT NULL,
    message    TEXT NOT NULL DEFAULT '',
    max_pages  INTEGER NOT NULL,
    stats      TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _connect():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.data_dir / "julia.db", timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        with _lock:
            yield conn
            conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
    jobs_mark_interrupted()


# ------------------------------------------------------------------ Wissensdatenbanken
def _kb(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    d["config"] = json.loads(d["config"])
    return d


def kb_create(name: str, description: str, collection: str, preset: str | None,
              source_type: str, config: dict) -> None:
    with _connect() as c:
        c.execute(
            "INSERT INTO kbs (name, description, collection, preset, source_type, config, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (name, description, collection, preset, source_type, json.dumps(config), now()),
        )


def kb_get(name: str) -> dict | None:
    with _connect() as c:
        return _kb(c.execute("SELECT * FROM kbs WHERE name=?", (name,)).fetchone())


def kb_list() -> list[dict]:
    with _connect() as c:
        return [_kb(r) for r in c.execute("SELECT * FROM kbs ORDER BY name").fetchall()]


def kb_delete(name: str) -> None:
    with _connect() as c:
        for table in ("pages", "plans", "jobs"):
            c.execute(f"DELETE FROM {table} WHERE kb=?", (name,))
        c.execute("DELETE FROM kbs WHERE name=?", (name,))


# ------------------------------------------------------------------ Seiten
def page_hash(kb: str, url: str) -> str | None:
    with _connect() as c:
        row = c.execute("SELECT hash FROM pages WHERE kb=? AND url=?", (kb, url)).fetchone()
    return row["hash"] if row else None


def page_put(kb: str, url: str, hash_: str, chunks: int, title: str) -> None:
    with _connect() as c:
        c.execute(
            "INSERT INTO pages (kb, url, hash, chunks, title, fetched_at) VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(kb, url) DO UPDATE SET hash=excluded.hash, chunks=excluded.chunks,"
            " title=excluded.title, fetched_at=excluded.fetched_at",
            (kb, url, hash_, chunks, title, now()),
        )


def page_stats(kb: str) -> tuple[int, int]:
    with _connect() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(chunks),0) AS c FROM pages WHERE kb=?", (kb,)
        ).fetchone()
    return int(row["n"]), int(row["c"])


# ------------------------------------------------------------------ Pläne
def plan_create(kb: str, plan: dict) -> str:
    plan_id = uuid.uuid4().hex[:10]
    with _connect() as c:
        c.execute(
            "INSERT INTO plans (id, kb, plan, created_at) VALUES (?,?,?,?)",
            (plan_id, kb, json.dumps(plan), now()),
        )
    return plan_id


def plan_get(plan_id: str) -> dict | None:
    with _connect() as c:
        row = c.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["plan"] = json.loads(d["plan"])
    return d


def plan_is_fresh(created_at: str) -> bool:
    created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created <= timedelta(hours=settings.plan_ttl_hours)


# ------------------------------------------------------------------ Jobs
def _job(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    d["stats"] = json.loads(d["stats"])
    return d


def job_create(kb: str, max_pages: int) -> str:
    job_id = uuid.uuid4().hex[:10]
    ts = now()
    with _connect() as c:
        c.execute(
            "INSERT INTO jobs (id, kb, status, message, max_pages, stats, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (job_id, kb, "running", "", max_pages, "{}", ts, ts),
        )
    return job_id


def job_update(job_id: str, status: str | None = None, message: str | None = None,
               stats: dict | None = None) -> None:
    sets, args = ["updated_at=?"], [now()]
    if status is not None:
        sets.append("status=?")
        args.append(status)
    if message is not None:
        sets.append("message=?")
        args.append(message)
    if stats is not None:
        sets.append("stats=?")
        args.append(json.dumps(stats))
    args.append(job_id)
    with _connect() as c:
        c.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id=?", args)


def job_get(job_id: str) -> dict | None:
    with _connect() as c:
        return _job(c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def job_list(kb: str | None = None, limit: int = 5) -> list[dict]:
    with _connect() as c:
        if kb:
            rows = c.execute(
                "SELECT * FROM jobs WHERE kb=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (kb, limit)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()
    return [_job(r) for r in rows]


def job_running() -> dict | None:
    with _connect() as c:
        return _job(c.execute("SELECT * FROM jobs WHERE status='running' LIMIT 1").fetchone())


def jobs_mark_interrupted() -> None:
    """Nach einem Neustart laufen keine Threads mehr: offene Jobs als unterbrochen markieren."""
    with _connect() as c:
        c.execute(
            "UPDATE jobs SET status='interrupted', message='Service wurde neu gestartet. "
            "Einfach erneut planen und starten, bereits gelernte Seiten werden übersprungen.', "
            "updated_at=? WHERE status='running'",
            (now(),),
        )
