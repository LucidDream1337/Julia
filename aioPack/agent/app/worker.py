"""Learning Worker: führt in festem Intervall Lernläufe aus (Standard: alle 24 h)."""
from __future__ import annotations

import logging
import signal
import threading
import time
from datetime import datetime

from .config import settings, setup_logging
from .learning import RunLock, execute_run, read_status

log = logging.getLogger("agent.worker")
stop = threading.Event()


def _seconds_until_next_run(interval: float) -> float:
    """Berücksichtigt den letzten Lauf, damit Container-Neustarts nicht ständig crawlen."""
    status = read_status()
    finished = status.get("finished_at")
    if finished:
        try:
            last = datetime.fromisoformat(finished).timestamp()
            return max(0.0, last + interval - time.time())
        except ValueError:
            pass
    return 0.0


def main() -> None:
    setup_logging()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    interval = settings.crawl_interval_hours * 3600
    wait = max(float(settings.worker_initial_delay_seconds), _seconds_until_next_run(interval))
    log.info(
        "Worker gestartet: Intervall %.1f h, erster Lauf in %d s, max. %d Seiten/Lauf",
        settings.crawl_interval_hours, int(wait), settings.max_pages_per_run,
    )

    while not stop.wait(wait):
        lock = RunLock()
        if lock.acquire():
            try:
                execute_run(trigger="worker")
            except Exception:
                log.exception("Lernlauf fehlgeschlagen")
            finally:
                lock.release()
        else:
            log.info("Es läuft bereits ein Lernlauf – überspringe diesen Zyklus.")
        wait = interval
    log.info("Worker beendet.")


if __name__ == "__main__":
    main()
