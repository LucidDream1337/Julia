"""SQLite-Zustand des Crawlers (Frontier, Hashes, Fehler). Liegt unter /data."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT NOT NULL UNIQUE,
    source        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    title         TEXT,
    content_hash  TEXT,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    fail_count    INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    discovered_at REAL NOT NULL,
    last_crawled  REAL
);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
"""

ERROR_RETRY_AFTER_SECONDS = 24 * 3600
MAX_FAILS = 3


class StateDB:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- Frontier -------------------------------------------------------
    def add_urls(self, source: str, urls: list[str]) -> int:
        now = time.time()
        added = 0
        with self._lock:
            for url in urls:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO pages (url, source, discovered_at) VALUES (?, ?, ?)",
                    (url, source, now),
                )
                added += cur.rowcount
            self._conn.commit()
        return added

    def next_batch(self, limit: int, recrawl_after_days: int) -> list[str]:
        now = time.time()
        rows = self._exec(
            """
            SELECT url FROM pages
            WHERE status = 'pending'
               OR (status = 'error' AND fail_count < ? AND last_crawled < ?)
               OR (status = 'ok' AND last_crawled < ?)
            ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'error' THEN 1 ELSE 2 END,
                     COALESCE(last_crawled, 0), id
            LIMIT ?
            """,
            (
                MAX_FAILS,
                now - ERROR_RETRY_AFTER_SECONDS,
                now - recrawl_after_days * 86400,
                limit,
            ),
        ).fetchall()
        return [r["url"] for r in rows]

    def get(self, url: str) -> sqlite3.Row | None:
        return self._exec("SELECT * FROM pages WHERE url = ?", (url,)).fetchone()

    # -- Statusänderungen -----------------------------------------------
    def mark_ok(self, url: str, title: str, content_hash: str, chunks: int) -> None:
        self._exec(
            """UPDATE pages SET status='ok', title=?, content_hash=?, chunk_count=?,
               fail_count=0, error=NULL, last_crawled=? WHERE url=?""",
            (title, content_hash, chunks, time.time(), url),
        )

    def touch_ok(self, url: str) -> None:
        self._exec(
            "UPDATE pages SET status='ok', fail_count=0, error=NULL, last_crawled=? WHERE url=?",
            (time.time(), url),
        )

    def mark_error(self, url: str, message: str) -> None:
        self._exec(
            """UPDATE pages SET status='error', fail_count=fail_count+1, error=?,
               last_crawled=? WHERE url=?""",
            (message[:500], time.time(), url),
        )

    def mark_status(self, url: str, status: str, message: str = "") -> None:
        """Endzustände: blocked (robots.txt), gone (404/410), skipped (nicht erlaubt)."""
        self._exec(
            "UPDATE pages SET status=?, error=?, chunk_count=0, last_crawled=? WHERE url=?",
            (status, message[:500] or None, time.time(), url),
        )

    # -- Statistik ------------------------------------------------------
    def stats(self) -> dict:
        rows = self._exec("SELECT status, COUNT(*) AS n FROM pages GROUP BY status").fetchall()
        by_status = {r["status"]: r["n"] for r in rows}
        chunks = self._exec(
            "SELECT COALESCE(SUM(chunk_count), 0) AS n FROM pages WHERE status='ok'"
        ).fetchone()["n"]
        return {"pages": by_status, "total_pages": sum(by_status.values()), "chunks": chunks}
