"""Generischer, höflicher Web-Crawler: Regeln, robots.txt, Fetcher, HTML-Parser, Crawl-Schleife.

Feste Grenzen (nicht abschaltbar): robots.txt ist bindend, mindestens MIN_CRAWL_DELAY Sekunden
Pause, nur GET, eine Verbindung, klarer User-Agent mit Kontakt, sofortiger Abbruch bei
HTTP 429/503 (und bei gehäuftem 403), keine Umgehung von Zugangsbeschränkungen.
"""
from __future__ import annotations

import logging
import re
import textwrap
import time
import urllib.robotparser
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterator
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from .chunking import Block
from .config import USER_AGENT_TOKEN, settings
from .errors import BadRequest, CrawlBlocked, RobotsBlocked, RobotsUnavailable

log = logging.getLogger(__name__)

DEFAULT_EXTENSIONS = (".html", ".htm", ".php", ".asp", ".aspx")
DEFAULT_SELECTORS = "main | article | #main | #content | body"


# --------------------------------------------------------------------------- Regeln
def _lower_tuple(values) -> tuple[str, ...]:
    return tuple(str(v).strip().lower() for v in (values or []) if str(v).strip())


@dataclass(frozen=True)
class WebRules:
    seeds: tuple[str, ...]
    hosts: frozenset[str]
    allowed_prefixes: tuple[str, ...]
    exclude_pattern: str
    content_selectors: tuple[str, ...]
    stop_headings: tuple[str, ...]
    skip_headings: tuple[str, ...]
    extensions: tuple[str, ...]
    delay: float

    @classmethod
    def from_config(cls, cfg: dict) -> "WebRules":
        seeds = tuple(str(s).strip() for s in (cfg.get("seeds") or []) if str(s).strip())
        if not seeds:
            raise BadRequest("Für eine Web-Quelle wird mindestens eine Start-URL (seeds) gebraucht.")
        hosts = set()
        for seed in seeds:
            parts = urlsplit(seed)
            if parts.scheme != "https" or not parts.netloc:
                raise BadRequest(f"Start-URL muss mit https:// beginnen: {seed}")
            hosts.add(parts.netloc.lower())
        pattern = str(cfg.get("exclude_pattern") or "")
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise BadRequest(f"exclude_pattern ist kein gültiger regulärer Ausdruck: {exc}") from exc
        selectors = tuple(
            s.strip() for s in str(cfg.get("content_selector") or DEFAULT_SELECTORS).split("|") if s.strip()
        )
        try:
            delay = float(cfg.get("delay_seconds", settings.min_delay))
        except (TypeError, ValueError):
            delay = settings.min_delay
        return cls(
            seeds=seeds,
            hosts=frozenset(hosts),
            allowed_prefixes=tuple(cfg.get("allowed_prefixes") or ["/"]),
            exclude_pattern=pattern,
            content_selectors=selectors,
            stop_headings=_lower_tuple(cfg.get("stop_headings")),
            skip_headings=_lower_tuple(cfg.get("skip_headings")),
            extensions=_lower_tuple(cfg.get("extensions")) or DEFAULT_EXTENSIONS,
            delay=max(settings.min_delay, delay),
        )

    def in_scope(self, url: str) -> bool:
        """Host, Pfadpräfix, Ausschlussmuster und Dateiendung prüfen."""
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc.lower() not in self.hosts:
            return False
        path = parts.path or "/"
        if not any(path.startswith(p) for p in self.allowed_prefixes):
            return False
        if self.exclude_pattern and re.search(self.exclude_pattern, path):
            return False
        last = path.rsplit("/", 1)[-1]
        if "." not in last:  # "/plants/abc-12/" oder "/plants/abc-12"
            return True
        return "." + last.rsplit(".", 1)[-1].lower() in self.extensions


def normalize_url(href: str | None, base: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    parts = urlsplit(urljoin(base, href))
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    # Query und Fragment werden bewusst verworfen (Tracking, Editor-Parameter).
    return urlunsplit(("https", parts.netloc.lower(), path, "", ""))


# --------------------------------------------------------------------------- Netzwerk
class Fetcher:
    """Eine Verbindung, feste Mindestpause, klarer User-Agent."""

    def __init__(self, delay: float) -> None:
        self.delay = max(settings.min_delay, delay)
        self._last = 0.0
        self._client = httpx.Client(
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5",
            },
            timeout=20.0,
            follow_redirects=True,
            max_redirects=3,
        )

    def raise_delay(self, seconds: float) -> None:
        self.delay = max(self.delay, seconds)

    def get(self, url: str):
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            return self._client.get(url)
        finally:
            self._last = time.monotonic()

    def close(self) -> None:
        self._client.close()


class RobotsGuard:
    """Lädt robots.txt je Host. Ist sie nicht sicher bewertbar, wird nicht gecrawlt."""

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _load(self, host: str) -> urllib.robotparser.RobotFileParser:
        try:
            resp = self._fetcher.get(f"https://{host}/robots.txt")
        except httpx.HTTPError as exc:
            raise RobotsUnavailable(f"robots.txt von {host} nicht abrufbar: {exc}") from exc
        parser = urllib.robotparser.RobotFileParser()
        if resp.status_code == 200:
            parser.parse(resp.text.splitlines())
        elif resp.status_code in (404, 410):
            parser.parse([])  # keine robots.txt -> alles erlaubt (RFC 9309)
        elif resp.status_code in (401, 403):
            parser.parse(["User-agent: *", "Disallow: /"])  # konservativ: gesperrt
        else:
            raise RobotsUnavailable(
                f"robots.txt von {host} lieferte HTTP {resp.status_code}: "
                "Crawl-Erlaubnis nicht prüfbar, Abbruch."
            )
        delay = parser.crawl_delay(USER_AGENT_TOKEN)
        if delay:
            try:
                self._fetcher.raise_delay(float(delay))
            except (TypeError, ValueError):
                pass
        return parser

    def can_fetch(self, url: str) -> bool:
        host = urlsplit(url).netloc.lower()
        if host not in self._parsers:
            self._parsers[host] = self._load(host)
        return self._parsers[host].can_fetch(USER_AGENT_TOKEN, url)


# --------------------------------------------------------------------------- Parsing
@dataclass
class ParsedPage:
    url: str
    title: str
    blocks: list[Block]
    links: list[str] = field(default_factory=list)


_NOISE = "script, style, noscript, iframe, svg, form, button, nav, header, footer, aside, .nextprev, .ads"
_BLOCKS = "h1, h2, h3, h4, p, li, pre, table, div.w3-code"
_WS = re.compile(r"\s+")


def _inline(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _code(el) -> str:
    for br in el.find_all("br"):
        br.replace_with("\n")
    text = textwrap.dedent(el.get_text("")).strip("\n")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_page(html: str, url: str, rules: WebRules) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")

    # Links zuerst einsammeln (das Seitenmenü enthält oft alle Lektionen).
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        link = normalize_url(a["href"], url)
        if link and link not in seen and rules.in_scope(link):
            seen.add(link)
            links.append(link)

    main = None
    for selector in rules.content_selectors:
        main = soup.select_one(selector)
        if main is not None:
            break
    if main is None:
        main = soup.body or soup
    for el in main.select(_NOISE):
        el.decompose()

    h1 = main.find("h1")
    title = _inline(h1.get_text("")) if h1 else ""
    if not title and soup.title and soup.title.string:
        title = _inline(soup.title.string)
    if not title:
        title = urlsplit(url).path.rsplit("/", 1)[-1] or urlsplit(url).netloc

    elements = main.select(_BLOCKS)
    selected = {id(e) for e in elements}
    blocks: list[Block] = []
    for el in elements:
        if any(id(parent) in selected for parent in el.parents):
            continue  # bereits im übergeordneten Element enthalten
        name = el.name
        if name in ("h1", "h2", "h3", "h4"):
            text = _inline(el.get_text(""))
            low = text.lower()
            if low in rules.stop_headings:
                break
            if not text or low in rules.skip_headings:
                continue
            blocks.append(Block("heading", text, level=int(name[1])))
        elif name == "pre" or (name == "div" and "w3-code" in (el.get("class") or [])):
            code = _code(el)
            if code:
                blocks.append(Block("code", code))
        elif name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [_inline(c.get_text("")) for c in tr.find_all(["th", "td"])]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append(Block("table", "\n".join(rows)))
        else:  # p, li
            text = _inline(el.get_text(""))
            if len(text) < 2:
                continue
            blocks.append(Block("text", ("- " + text) if name == "li" else text))
    return ParsedPage(url=url, title=title, blocks=blocks, links=links)


# --------------------------------------------------------------------------- Crawler
@dataclass
class Loaded:
    url: str
    page: ParsedPage | None = None
    skip: str = ""
    error: str = ""
    robots_blocked: bool = False


class WebCrawler:
    def __init__(self, rules: WebRules) -> None:
        self.rules = rules
        self.fetcher = Fetcher(rules.delay)
        self.robots = RobotsGuard(self.fetcher)
        self._denied = 0

    def close(self) -> None:
        self.fetcher.close()

    def load(self, url: str) -> Loaded:
        """Eine Seite holen und parsen. Wirft CrawlBlocked bei 429/503 bzw. gehäuftem 403."""
        if not self.robots.can_fetch(url):
            return Loaded(url, skip="robots.txt verbietet diese URL", robots_blocked=True)
        try:
            resp = self.fetcher.get(url)
        except httpx.HTTPError as exc:
            return Loaded(url, error=f"Netzwerkfehler: {exc}")
        code = resp.status_code
        if code in (429, 503):
            raise CrawlBlocked(f"{urlsplit(url).netloc} antwortet mit HTTP {code}. Abbruch, um den Server nicht zu belasten.")
        if code == 403:
            self._denied += 1
            if self._denied >= 5:
                raise CrawlBlocked(f"{urlsplit(url).netloc} verweigert den Zugriff (mehrfach HTTP 403). Abbruch.")
            return Loaded(url, error="HTTP 403")
        if code in (404, 410):
            return Loaded(url, skip=f"HTTP {code}")
        if code >= 400:
            return Loaded(url, error=f"HTTP {code}")
        self._denied = 0
        ctype = resp.headers.get("content-type", "").lower()
        if "html" not in ctype:
            return Loaded(url, skip=f"kein HTML ({ctype or 'unbekannt'})")
        final = normalize_url(str(resp.url), url) or url
        if final != url and not (self.rules.in_scope(final) or final in self.rules.seeds):
            return Loaded(url, skip="Weiterleitung aus dem erlaubten Bereich")
        try:
            return Loaded(final, page=parse_page(resp.text, final, self.rules))
        except Exception as exc:  # defektes HTML darf den Lauf nicht beenden
            return Loaded(final, error=f"Parsefehler: {exc}")

    def crawl(self, max_pages: int, should_stop: Callable[[], bool]) -> Iterator[Loaded]:
        """Breitensuche ab den Start-URLs. Liefert jede abgerufene Seite (auch Fehler/Skips)."""
        queue: deque[str] = deque()
        seen: set[str] = set()
        seed_set = {normalize_url(s, s) or s for s in self.rules.seeds}
        for seed in seed_set:
            seen.add(seed)
            queue.append(seed)
        pages = 0
        while queue and pages < max_pages:
            if should_stop():
                return
            url = queue.popleft()
            if url not in seed_set and not self.rules.in_scope(url):
                continue
            loaded = self.load(url)
            if loaded.robots_blocked and url in seed_set:
                raise RobotsBlocked(f"robots.txt verbietet das Crawlen der Start-URL {url}.")
            if loaded.page is not None:
                pages += 1
                if loaded.url != url:
                    seen.add(loaded.url)
                for link in loaded.page.links:
                    if link not in seen:
                        seen.add(link)
                        queue.append(link)
            yield loaded
