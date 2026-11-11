"""Kommandozeile für Admin-Aufgaben direkt im Container (ohne HTTP/Token):

  docker exec julia-school-agent python -m app.cli status
  docker exec julia-school-agent python -m app.cli learn --max-pages 10
  docker exec julia-school-agent python -m app.cli crawl https://www.w3schools.com/python/python_lists.asp
  docker exec julia-school-agent python -m app.cli ask "Was ist eine Python-Liste?"
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import setup_logging
from .errors import OllamaError, StoreError
from .learning import RunLock, execute_run, read_status


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_learn = sub.add_parser("learn", help="regulären Lernlauf ausführen")
    p_learn.add_argument("--max-pages", type=int, default=None)

    p_crawl = sub.add_parser("crawl", help="bestimmte URLs (neu) indexieren")
    p_crawl.add_argument("urls", nargs="+")

    sub.add_parser("status", help="Status des letzten Laufs anzeigen")

    p_ask = sub.add_parser("ask", help="Testfrage an die RAG-Pipeline")
    p_ask.add_argument("question")
    p_ask.add_argument("--no-generate", action="store_true")

    args = parser.parse_args()

    if args.cmd == "status":
        print(json.dumps(read_status(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "ask":
        from . import rag
        try:
            result = rag.ask(args.question, generate=not args.no_generate)
        except (OllamaError, StoreError) as exc:
            print(f"Fehler: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    lock = RunLock()
    if not lock.acquire():
        print("Es läuft bereits ein Lernlauf.", file=sys.stderr)
        return 1
    try:
        if args.cmd == "learn":
            summary = execute_run(max_pages=args.max_pages, trigger="cli-learn")
        else:
            summary = execute_run(urls=args.urls, trigger="cli-crawl")
    finally:
        lock.release()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["state"] == "finished" else 1


if __name__ == "__main__":
    sys.exit(main())
