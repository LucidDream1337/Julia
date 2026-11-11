"""RAG-Pipeline: Frage -> (Suchanfrage) -> Embedding -> Qdrant -> Kontext -> Sprachmodell."""
from __future__ import annotations

import logging
from typing import Any

from . import llm
from .config import settings
from .embeddings import OllamaEmbedder
from .store import Store

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Du bist ein geduldiger Programmierlehrer. Beantworte die Frage des Lernenden "
    "ausschließlich anhand der nummerierten Lernmaterial-Auszüge unten. "
    "Antworte in der Sprache der Frage. Erkläre Schritt für Schritt, zeige kurze "
    "Codebeispiele in Markdown-Codeblöcken und verweise mit [1], [2] usw. auf die "
    "Auszüge, die du verwendet hast. Wenn die Auszüge die Frage nicht beantworten, "
    "sage das klar und erfinde nichts."
)

REWRITE_PROMPT = (
    "Rewrite the following programming question as a short English search query "
    "(maximum 12 words) for a programming tutorial website. "
    "Output only the query, nothing else.\n\nQuestion: {question}"
)

_embedder: OllamaEmbedder | None = None
_store: Store | None = None


def _get_embedder() -> OllamaEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = OllamaEmbedder()
    return _embedder


def _get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def rewrite_query(question: str) -> str:
    """Nomic-Embeddings sind überwiegend englisch; die Quellen ebenfalls."""
    if not settings.query_rewrite:
        return question
    try:
        rewritten = llm.chat(
            [{"role": "user", "content": REWRITE_PROMPT.format(question=question)}],
            temperature=0.0,
            num_predict=48,
        )
    except Exception as exc:  # Rewrite ist optional – Fehler dürfen die Suche nicht stoppen
        log.warning("Query-Rewrite fehlgeschlagen, nutze Originalfrage: %s", exc)
        return question
    rewritten = rewritten.strip().strip('"').strip("'").splitlines()[0] if rewritten.strip() else ""
    if not rewritten or len(rewritten) > 200:
        return question
    return rewritten


def _build_context(hits: list[dict]) -> tuple[str, list[dict]]:
    parts: list[str] = []
    used: list[dict] = []
    total = 0
    for hit in hits:
        header = f"[{len(used) + 1}] {hit.get('title', '')}"
        if hit.get("section"):
            header += f" – {hit['section']}"
        block = f"{header}\n{hit.get('text', '')}"
        if used and total + len(block) > settings.max_context_chars:
            break
        parts.append(block)
        used.append(hit)
        total += len(block)
    return "\n\n---\n\n".join(parts), used


def ask(question: str, top_k: int | None = None, generate: bool = True) -> dict[str, Any]:
    question = question.strip()
    k = top_k or settings.top_k
    search_query = rewrite_query(question)

    vector = _get_embedder().embed_query(search_query)
    hits = _get_store().search(vector, limit=k, min_score=settings.min_score)
    context, used = _build_context(hits)

    sources = [
        {
            "number": i,
            "title": h.get("title", ""),
            "section": h.get("section", ""),
            "url": h.get("url", ""),
            "score": round(h["score"], 3),
            "excerpt": h.get("text", "") if not generate else "",
        }
        for i, h in enumerate(used, start=1)
    ]

    if not used:
        return {
            "question": question,
            "search_query": search_query,
            "answer": (
                "In der lokalen Wissensdatenbank wurden keine passenden Lerninhalte gefunden. "
                "Entweder wurde das Thema noch nicht gelernt (Lernlauf prüfen) oder die Frage "
                "ist zu unspezifisch."
            ),
            "sources": [],
            "knowledge_found": False,
        }

    if not generate:
        return {
            "question": question,
            "search_query": search_query,
            "answer": None,
            "sources": sources,
            "knowledge_found": True,
        }

    answer = llm.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Lernmaterial-Auszüge:\n\n{context}\n\nFrage: {question}",
            },
        ],
        temperature=0.2,
    )
    source_lines = "\n".join(
        f"[{s['number']}] {s['title']}" + (f" – {s['section']}" if s["section"] else "")
        + f" – {s['url']}"
        for s in sources
    )
    return {
        "question": question,
        "search_query": search_query,
        "answer": f"{answer}\n\nQuellen:\n{source_lines}",
        "sources": sources,
        "knowledge_found": True,
    }
