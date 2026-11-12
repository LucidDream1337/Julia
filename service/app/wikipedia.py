"""Wikipedia über die offizielle MediaWiki-API (kein Crawlen der normalen Seiten).

Regeln laut Wikimedia: aussagekräftiger User-Agent mit Kontakt, Anfragen nacheinander,
bei HTTP 429/503 aufhören. Inhalte stehen unter CC BY-SA 4.0 (Quelle bleibt im Payload).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from .config import settings
from .errors import BadRequest, CrawlBlocked

_LANG = re.compile(r"^[a-z]{2,3}(-[a-z]{2,8})?$")
LICENSE = "CC BY-SA 4.0 (Wikipedia-Autoren)"


@dataclass
class WikiPage:
    title: str
    url: str
    text: str


class WikiClient:
    def __init__(self, cfg: dict) -> None:
        lang = str(cfg.get("lang") or "de").lower()
        if not _LANG.match(lang):
            raise BadRequest(f"Ungültiger Sprachcode für Wikipedia: {lang!r} (z. B. 'de', 'en', 'simple').")
        if not settings.contact:
            raise BadRequest(
                "CRAWLER_CONTACT ist nicht gesetzt. Wikimedia verlangt einen User-Agent mit "
                "Kontaktangabe. Bitte E-Mail oder URL in die .env eintragen und den Stack neu starten."
            )
        self.lang = lang
        self.api = f"https://{lang}.wikipedia.org/w/api.php"
        try:
            delay = float(cfg.get("delay_seconds", 1.0))
        except (TypeError, ValueError):
            delay = 1.0
        self.delay = max(1.0, delay)
        self._last = 0.0
        self._client = httpx.Client(
            headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
            timeout=30.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, params: dict) -> dict:
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        query = {"action": "query", "format": "json", "formatversion": "2", **params}
        try:
            resp = self._client.get(self.api, params=query)
        finally:
            self._last = time.monotonic()
        if resp.status_code in (429, 503):
            raise CrawlBlocked(f"Wikipedia antwortet mit HTTP {resp.status_code}. Abbruch.")
        if resp.status_code == 403:
            raise CrawlBlocked(
                "Wikipedia verweigert den Zugriff (HTTP 403). Prüfe CRAWLER_CONTACT (gültiger Kontakt im User-Agent)."
            )
        resp.raise_for_status()
        return resp.json()

    # ---------------------------------------------------------------- Titel finden
    def category_members(self, category: str, depth: int, limit: int) -> list[str]:
        name = category if ":" in category else f"Category:{category}"
        titles: list[str] = []
        seen_cats = {name}
        queue = [(name, 0)]
        while queue and len(titles) < limit:
            cat, level = queue.pop(0)
            cont: dict = {}
            while len(titles) < limit:
                data = self._get({
                    "list": "categorymembers", "cmtitle": cat, "cmlimit": "500",
                    "cmtype": "page|subcat", **cont,
                })
                for member in data.get("query", {}).get("categorymembers", []):
                    if member.get("ns") == 0:
                        if member["title"] not in titles:
                            titles.append(member["title"])
                    elif member.get("ns") == 14 and level < depth and member["title"] not in seen_cats:
                        seen_cats.add(member["title"])
                        queue.append((member["title"], level + 1))
                cont = data.get("continue") or {}
                if not cont:
                    break
        return titles[:limit]

    def search(self, query: str, limit: int) -> list[str]:
        titles: list[str] = []
        cont: dict = {}
        while len(titles) < limit:
            data = self._get({
                "list": "search", "srsearch": query, "srnamespace": "0",
                "srlimit": str(min(50, limit)), **cont,
            })
            for hit in data.get("query", {}).get("search", []):
                if hit["title"] not in titles:
                    titles.append(hit["title"])
            cont = data.get("continue") or {}
            if not cont:
                break
        return titles[:limit]

    def resolve_titles(self, cfg: dict, cap: int) -> list[str]:
        titles: list[str] = []

        def add(items) -> None:
            for t in items:
                if t not in titles and len(titles) < cap:
                    titles.append(t)

        add(str(t).strip() for t in (cfg.get("titles") or []) if str(t).strip())
        for entry in cfg.get("categories") or []:
            if isinstance(entry, str):
                entry = {"name": entry}
            if not isinstance(entry, dict) or not entry.get("name"):
                raise BadRequest("categories: erwartet Einträge wie {\"name\": \"Kategorie:Botanik\", \"depth\": 1}.")
            depth = max(0, min(3, int(entry.get("depth", 1))))
            add(self.category_members(str(entry["name"]), depth, cap - len(titles)))
        if cfg.get("search"):
            add(self.search(str(cfg["search"]), cap - len(titles)))
        if not titles:
            raise BadRequest(
                "Keine Artikel gefunden. Gib titles, categories oder search an "
                "(z. B. {\"categories\": [{\"name\": \"Kategorie:Heilpflanze\", \"depth\": 1}]})."
            )
        return titles

    # ---------------------------------------------------------------- Artikel holen
    def extract(self, title: str) -> WikiPage | None:
        data = self._get({
            "prop": "extracts", "explaintext": "1", "exsectionformat": "wiki",
            "redirects": "1", "titles": title,
        })
        pages = data.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            return None
        page = pages[0]
        text = (page.get("extract") or "").strip()
        if not text:
            return None
        real = page.get("title") or title
        url = f"https://{self.lang}.wikipedia.org/wiki/{quote(real.replace(' ', '_'), safe='_()')}"
        return WikiPage(title=real, url=url, text=text)
