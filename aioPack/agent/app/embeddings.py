"""Embeddings über den bestehenden Ollama-Container (nomic-embed-text)."""
from __future__ import annotations

import logging

import httpx

from .config import settings
from .errors import OllamaError

log = logging.getLogger(__name__)

# nomic-embed-text erwartet Task-Präfixe; das verbessert die Suchqualität spürbar.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class OllamaEmbedder:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.ollama_base_url, timeout=settings.ollama_timeout
        )
        self._model = settings.ollama_embedding_model

    # -- intern ---------------------------------------------------------
    def _embed_batch(self, inputs: list[str]) -> list[list[float]]:
        try:
            resp = self._client.post(
                "/api/embed",
                json={"model": self._model, "input": inputs, "truncate": True},
            )
            if resp.status_code == 404:
                text = resp.text.lower()
                if "model" in text and "not found" in text:
                    raise OllamaError(
                        f"Embedding-Modell '{self._model}' fehlt in Ollama. "
                        f"Installieren mit: docker exec julia-school-ollama "
                        f"ollama pull {self._model}"
                    )
                # Sehr alte Ollama-Version ohne /api/embed -> Legacy-Endpunkt.
                return [self._embed_legacy(item) for item in inputs]
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise OllamaError(
                f"Ollama nicht erreichbar oder fehlerhaft ({settings.ollama_base_url}): {exc}"
            ) from exc
        except ValueError as exc:
            raise OllamaError(f"Ungültige Antwort von Ollama: {exc}") from exc

        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(inputs) or not vectors[0]:
            raise OllamaError("Ollama lieferte keine gültigen Embeddings.")
        return vectors

    def _embed_legacy(self, text: str) -> list[float]:
        try:
            resp = self._client.post(
                "/api/embeddings", json={"model": self._model, "prompt": text}
            )
            resp.raise_for_status()
            vector = resp.json().get("embedding")
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"Embedding-Anfrage fehlgeschlagen: {exc}") from exc
        if not vector:
            raise OllamaError("Ollama lieferte kein Embedding.")
        return vector

    # -- öffentlich -----------------------------------------------------
    def embed_documents(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = [DOC_PREFIX + t for t in texts[start : start + batch_size]]
            out.extend(self._embed_batch(batch))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([QUERY_PREFIX + text])[0]

    def close(self) -> None:
        self._client.close()
