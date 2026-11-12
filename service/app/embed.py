"""Embeddings über Ollama (/api/embed). Standardmodell: bge-m3 (mehrsprachig)."""
from __future__ import annotations

import httpx

from .config import settings
from .errors import OllamaError

_embedder: "Embedder | None" = None


class Embedder:
    def __init__(self) -> None:
        self._client = httpx.Client(base_url=settings.ollama_url, timeout=120.0)
        self.model = settings.embed_model
        # nomic-embed-text erwartet Task-Präfixe, bge-m3 nicht.
        nomic = self.model.lower().startswith("nomic-embed-text")
        self._doc_prefix = "search_document: " if nomic else ""
        self._query_prefix = "search_query: " if nomic else ""

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        try:
            resp = self._client.post(
                "/api/embed", json={"model": self.model, "input": inputs, "truncate": True}
            )
            if resp.status_code == 404:
                raise OllamaError(
                    f"Embedding-Modell '{self.model}' fehlt in Ollama. Installieren mit: "
                    f"docker exec julia-ollama ollama pull {self.model}"
                )
            resp.raise_for_status()
            vectors = resp.json().get("embeddings")
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama nicht erreichbar oder fehlerhaft ({settings.ollama_url}): {exc}") from exc
        except ValueError as exc:
            raise OllamaError(f"Ungültige Antwort von Ollama: {exc}") from exc
        if not isinstance(vectors, list) or len(vectors) != len(inputs) or not vectors[0]:
            raise OllamaError("Ollama lieferte keine gültigen Embeddings.")
        return vectors

    def embed_documents(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = [self._doc_prefix + t for t in texts[start:start + batch_size]]
            out.extend(self._embed(batch))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self._query_prefix + text])[0]


def get() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
