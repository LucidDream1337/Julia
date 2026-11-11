"""Qdrant-Zugriff: Collection-Verwaltung, Upsert pro Seite, Suche."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .config import settings
from .errors import StoreError

log = logging.getLogger(__name__)


def point_id(url: str, index: int) -> str:
    """Deterministische ID -> erneutes Indexieren überschreibt statt zu duplizieren."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{index}"))


class Store:
    def __init__(self) -> None:
        kwargs: dict[str, Any] = {
            "url": settings.qdrant_url,
            "api_key": settings.qdrant_api_key or None,
            "timeout": 30,
        }
        try:
            # Verhindert Versions-Warnungen, wenn Server (latest) und Client abweichen.
            self.client = QdrantClient(check_compatibility=False, **kwargs)
        except TypeError:
            self.client = QdrantClient(**kwargs)
        self.collection = settings.collection_name

    @staticmethod
    def _call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except StoreError:
            raise
        except Exception as exc:  # qdrant-client wirft diverse Exception-Typen
            raise StoreError(f"Qdrant-Fehler ({settings.qdrant_url}): {exc}") from exc

    # -- Collection -----------------------------------------------------
    def exists(self) -> bool:
        return bool(self._call(self.client.collection_exists, self.collection))

    def vector_size(self) -> int | None:
        info = self._call(self.client.get_collection, self.collection)
        vectors = info.config.params.vectors
        if isinstance(vectors, dict):  # benannte Vektoren – hier nicht erwartet
            vectors = next(iter(vectors.values()), None)
        return getattr(vectors, "size", None)

    def ensure_collection(self, dim: int) -> None:
        """Legt die Collection mit der tatsächlich ermittelten Dimension an."""
        if not self.exists():
            log.info("Lege Collection '%s' an (Dimension %d, Cosine)", self.collection, dim)
            self._call(
                self.client.create_collection,
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
            )
            self._call(
                self.client.create_payload_index,
                collection_name=self.collection,
                field_name="url",
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
            return
        existing = self.vector_size()
        if existing is not None and existing != dim:
            raise StoreError(
                f"Collection '{self.collection}' hat Dimension {existing}, das Embedding-Modell "
                f"liefert aber {dim}. Wurde das Embedding-Modell gewechselt? Dann eine neue "
                f"COLLECTION_NAME wählen oder die alte Collection löschen und neu lernen lassen."
            )

    def count(self) -> int:
        if not self.exists():
            return 0
        return int(self._call(self.client.count, self.collection, exact=True).count)

    # -- Schreiben ------------------------------------------------------
    def replace_page(self, url: str, points: list[qm.PointStruct]) -> None:
        """Upsert der neuen Chunks, danach Entfernen veralteter Chunks derselben URL."""
        for start in range(0, len(points), 64):
            self._call(
                self.client.upsert,
                collection_name=self.collection,
                points=points[start : start + 64],
                wait=True,
            )
        keep_ids = [p.id for p in points]
        url_match = qm.FieldCondition(key="url", match=qm.MatchValue(value=url))
        flt = qm.Filter(must=[url_match])
        if keep_ids:
            flt = qm.Filter(must=[url_match], must_not=[qm.HasIdCondition(has_id=keep_ids)])
        self._call(
            self.client.delete,
            collection_name=self.collection,
            points_selector=qm.FilterSelector(filter=flt),
            wait=True,
        )

    def delete_page(self, url: str) -> None:
        if not self.exists():
            return
        flt = qm.Filter(
            must=[qm.FieldCondition(key="url", match=qm.MatchValue(value=url))]
        )
        self._call(
            self.client.delete,
            collection_name=self.collection,
            points_selector=qm.FilterSelector(filter=flt),
            wait=True,
        )

    # -- Lesen ----------------------------------------------------------
    def search(self, vector: list[float], limit: int, min_score: float) -> list[dict]:
        if not self.exists():
            return []
        result = self._call(
            self.client.query_points,
            collection_name=self.collection,
            query=vector,
            limit=limit,
            score_threshold=min_score,
            with_payload=True,
        )
        return [
            {"score": float(p.score), **(p.payload or {})} for p in result.points
        ]
