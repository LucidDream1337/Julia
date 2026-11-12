"""Text -> Blöcke -> Chunks. Reine Funktionen ohne Netzwerk (gut testbar)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass
class Block:
    kind: str  # "heading" | "text" | "code" | "table"
    text: str
    level: int = 0


@dataclass
class Chunk:
    section: str
    text: str


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
    """Fasst Blöcke zu Chunks bis max_chars zusammen; Überschriften bleiben beim Text."""
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


_WIKI_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1$")

WIKI_STOP_HEADINGS = frozenset(
    {
        "references", "external links", "see also", "further reading", "notes",
        "bibliography", "sources", "footnotes",
        "einzelnachweise", "weblinks", "literatur", "siehe auch", "anmerkungen",
        "fußnoten", "quellen",
    }
)


def text_to_blocks(text: str, stop_headings: frozenset[str] = WIKI_STOP_HEADINGS) -> list[Block]:
    """Wikipedia-Klartext ('== Überschrift ==' + Absätze) in Blöcke umwandeln.

    Jede nicht leere Zeile ist ein Absatz. Ab einer Stopp-Überschrift (Literatur,
    Weblinks, ...) wird abgeschnitten.
    """
    blocks: list[Block] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _WIKI_HEADING.match(line)
        if match:
            title = match.group(2).strip()
            if title.lower() in stop_headings:
                break
            blocks.append(Block("heading", title, level=len(match.group(1))))
        else:
            blocks.append(Block("text", line))
    return blocks
