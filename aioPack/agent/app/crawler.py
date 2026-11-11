"""Crawler-Bausteine: Quellen-Definition, robots.txt, höflicher Fetcher, HTML-Parser, Chunking.

Weitere Wissensquellen ergänzt man, indem man in SOURCES ein weiteres `Source`-Objekt
einträgt (Host, Startseiten, erlaubte Pfade, CSS-Selektor des Hauptinhalts).
"""
from __future__ import annotations

import hashlib
import logging
import re
import textwrap
import time
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from .config import USER_AGENT_TOKEN, settings
from .errors import RobotsUnavailable

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Quellen
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Source:
    name: str
    host: str
    seeds: tuple[str, ...]
    allowed_prefixes: tuple[str, ...]
    exclude_pattern: str
    content_selector: str
    stop_headings: tuple[str, ...] = ()
    skip_headings: tuple[str, ...] = ()

    def accepts(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc.lower() != self.host:
            return False
        path = parts.path
        if not any(path.startswith(p) for p in self.allowed_prefixes):
            return False
        if re.search(self.exclude_pattern, path):
            return False
        return path.endswith((".asp", ".php")) or path.endswith("/")


W3SCHOOLS = Source(
    name="w3schools",
    host="www.w3schools.com",
    seeds=(
        "https://www.w3schools.com/python/default.asp",
        "https://www.w3schools.com/js/default.asp",
        "https://www.w3schools.com/html/default.asp",
        "https://www.w3schools.com/css/default.asp",
        "https://www.w3schools.com/sql/default.asp",
        "https://www.w3schools.com/java/default.asp",
        "https://www.w3schools.com/cpp/default.asp",
        "https://www.w3schools.com/c/index.php",
        "https://www.w3schools.com/cs/index.php",
        "https://www.w3schools.com/php/default.asp",
    ),
    allowed_prefixes=(
        "/python/", "/js/", "/html/", "/css/", "/sql/", "/java/", "/cpp/", "/c/", "/cs/", "/php/",
    ),
    # Übungen, Quizze, Zertifikate, "Try it"-Editor usw. sind keine Lerntexte.
    exclude_pattern=r"(?i)(tryit|trypython|tryjs|exercise|quiz|certificat|bootcamp|syllabus|study_plan|interview)",
    content_selector="#main",
    stop_headings=(
        "color picker", "report error", "thank you for helping us!", "top tutorials",
        "top references", "top examples", "get certified", "get certified!", "spaces",
        "upgrade", "w3schools is optimized for learning and training.",
    ),
    skip_headings=("example", "try it yourself", "try it yourself »"),
)

SOURCES: tuple[Source, ...] = (W3SCHOOLS,)


def source_for_url(url: str) -> Source | None:
    host = urlsplit(url).netloc.lower()
    for source in SOURCES:
        if source.host == host:
            return source
    return None


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


# --------------------------------------------------------------------------
# Netzwerk: höflicher Fetcher + robots.txt
# --------------------------------------------------------------------------
class Fetcher:
    def __init__(self, min_delay: float | None = None) -> None:
        self.delay = max(2.0, min_delay if min_delay is not None else settings.crawl_delay_seconds)
        self._last = 0.0
        self._client = httpx.Client(
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5",
                "Accept-Language": "en",
            },
            timeout=20.0,
            follow_redirects=True,
            max_redirects=3,
        )

    def raise_delay(self, seconds: float) -> None:
        self.delay = max(self.delay, seconds)

    def get(self, url: str) -> httpx.Response:
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
    """Lädt robots.txt je Host. Kann sie nicht sicher bewertet werden -> Abbruch."""

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _load(self, host: str) -> urllib.robotparser.RobotFileParser:
        url = f"https://{host}/robots.txt"
        try:
            resp = self._fetcher.get(url)
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
                f"robots.txt von {host} lieferte HTTP {resp.status_code} – "
                "Crawl-Erlaubnis nicht prüfbar, Abbruch."
            )

        delay = parser.crawl_delay(USER_AGENT_TOKEN)
        if delay:
            try:
                self._fetcher.raise_delay(float(delay))
            except (TypeError, ValueError):
                pass
        log.info("robots.txt für %s geladen (HTTP %d)", host, resp.status_code)
        return parser

    def can_fetch(self, url: str) -> bool:
        host = urlsplit(url).netloc.lower()
        if host not in self._parsers:
            self._parsers[host] = self._load(host)
        return self._parsers[host].can_fetch(USER_AGENT_TOKEN, url)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
class ParseError(RuntimeError):
    pass


@dataclass
class Block:
    kind: str  # "heading" | "text" | "code" | "table"
    text: str
    level: int = 0


@dataclass
class ParsedPage:
    url: str
    title: str
    topic: str
    blocks: list[Block]
    links: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    section: str
    text: str


_NOISE_SELECTOR = "script, style, noscript, iframe, svg, form, button, nav, .nextprev, .ads"
_BLOCK_SELECTOR = "h1, h2, h3, h4, p, li, pre, table, div.w3-code"
_WS = re.compile(r"\s+")


def _clean_inline(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _clean_code(el) -> str:
    for br in el.find_all("br"):
        br.replace_with("\n")
    text = textwrap.dedent(el.get_text("")).strip("\n")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_page(html: str, url: str, source: Source) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")

    # Links vor dem Entfernen von Rauschen einsammeln (Seitenmenü enthält die Lektionen).
    links: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        link = normalize_url(a["href"], url)
        if link and link not in seen and source.accepts(link):
            seen.add(link)
            links.append(link)

    main = soup.select_one(source.content_selector)
    if main is None:
        raise ParseError(f"Hauptinhalt ('{source.content_selector}') nicht gefunden")
    for el in main.select(_NOISE_SELECTOR):
        el.decompose()

    h1 = main.find("h1")
    title = _clean_inline(h1.get_text("")) if h1 else ""
    if not title and soup.title and soup.title.string:
        title = _clean_inline(soup.title.string)
    if not title:
        title = urlsplit(url).path.rsplit("/", 1)[-1]

    elements = main.select(_BLOCK_SELECTOR)
    selected = {id(e) for e in elements}
    blocks: list[Block] = []
    for el in elements:
        if any(id(parent) in selected for parent in el.parents):
            continue  # bereits im übergeordneten Element enthalten
        name = el.name
        if name in ("h1", "h2", "h3", "h4"):
            text = _clean_inline(el.get_text(""))
            low = text.lower()
            if low in source.stop_headings:
                break
            if not text or low in source.skip_headings:
                continue
            blocks.append(Block("heading", text, level=int(name[1])))
        elif name == "pre" or (name == "div" and "w3-code" in (el.get("class") or [])):
            code = _clean_code(el)
            if code:
                blocks.append(Block("code", code))
        elif name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [_clean_inline(c.get_text("")) for c in tr.find_all(["th", "td"])]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append(Block("table", "\n".join(rows)))
        else:  # p, li
            text = _clean_inline(el.get_text(""))
            if len(text) < 2:
                continue
            if name == "li":
                text = "- " + text
            blocks.append(Block("text", text))

    segments = [s for s in urlsplit(url).path.split("/") if s]
    topic = segments[0] if segments else ""
    return ParsedPage(url=url, title=title, topic=topic, blocks=blocks, links=links)


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------
def _split_lines(text: str, limit: int) -> list[str]:
    """Teilt an Zeilengrenzen; überlange Einzelzeilen werden hart getrennt."""
    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]
        if current and len(current) + len(line) + 1 > limit:
            parts.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        parts.append(current)
    return parts


def _render(block: Block, max_chars: int) -> list[str]:
    if block.kind == "heading":
        return [f"{'#' * max(1, block.level)} {block.text}"]
    if block.kind == "code":
        if len(block.text) + 8 <= max_chars:
            return [f"```\n{block.text}\n```"]
        return [f"```\n{part}\n```" for part in _split_lines(block.text, max_chars - 8)]
    if len(block.text) <= max_chars:
        return [block.text]
    return _split_lines(block.text, max_chars)


def build_chunks(blocks: list[Block], max_chars: int, min_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_len = 0
    last_is_heading = False
    section = ""
    chunk_section = ""

    def flush() -> None:
        nonlocal buf, buf_len, last_is_heading
        text = "\n\n".join(buf).strip()
        if text:
            chunks.append(Chunk(section=chunk_section, text=text))
        buf, buf_len, last_is_heading = [], 0, False

    for block in blocks:
        is_heading = block.kind == "heading"
        if is_heading:
            if buf_len >= min_chars:
                flush()
            section = block.text
        for part in _render(block, max_chars):
            if buf and buf_len + len(part) + 2 > max_chars:
                carry = buf.pop() if (last_is_heading and len(buf) > 1) else None
                if carry is not None:
                    buf_len -= len(carry) + 2
                flush()
                if carry is not None:
                    buf.append(carry)
                    buf_len += len(carry) + 2
                    last_is_heading = True
            if not buf:
                chunk_section = section
            buf.append(part)
            buf_len += len(part) + 2
            last_is_heading = is_heading
    flush()
    return chunks


def content_hash(title: str, chunks: list[Chunk]) -> str:
    h = hashlib.sha256()
    h.update(title.encode("utf-8"))
    for chunk in chunks:
        h.update(b"\x00")
        h.update(chunk.text.encode("utf-8"))
    return h.hexdigest()
