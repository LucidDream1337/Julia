"""Qdrant-Zugriff: eine Collection je Wissensdatenbank."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .config import settings
from .errors import StoreError

log = logging.getLogger(__name__)
_client: QdrantClient | None = None


def client() -> QdrantClient:
    global _client
    if _client is None:
        kwargs: dict[str, Any] = {"url": settings.qdrant_url, "timeout": 30}
        try:
            _client = QdrantClient(check_compatibility=False, **kwargs)
        except TypeError:  # ältere qdrant-client-Versionen kennen den Parameter nicht
            _client = QdrantClient(**kwargs)
    return _client


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except StoreError:
        raise
    except Exception as exc:  # qdrant-client wirft diverse Exception-Typen
        raise StoreError(f"Qdrant-Fehler ({settings.qdrant_url}): {exc}") from exc


def collection_name(kb: str) -> str:
    return f"kb_{kb}"


def point_id(url: str, index: int) -> str:
    """Deterministische ID: erneutes Indexieren überschreibt statt zu duplizieren."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{index}"))


def make_point(url: str, index: int, vector: list[float], payload: dict) -> qm.PointStruct:
    return qm.PointStruct(id=point_id(url, index), vector=vector, payload=payload)


def exists(collection: str) -> bool:
    return bool(_call(client().collection_exists, collection))


def ensure(collection: str, dim: int) -> None:
    if not exists(collection):
        log.info("Lege Collection %s an (Dimension %d)", collection, dim)
        _call(
            client().create_collection,
            collection_name=collection,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        _call(
            client().create_payload_index,
            collection_name=collection,
            field_name="url",
            field_schema=qm.PayloadSchemaType.KEYWORD,
        )
        return
    info = _call(client().get_collection, collection)
    vectors = info.config.params.vectors
    if isinstance(vectors, dict):
        vectors = next(iter(vectors.values()), None)
    existing = getattr(vectors, "size", None)
    if existing is not None and existing != dim:
        raise StoreError(
            f"Collection {collection} hat Dimension {existing}, das Embedding-Modell liefert {dim}. "
            "Wurde EMBED_MODEL gewechselt? Dann die Wissensdatenbank löschen und neu anlegen."
        )


def count(collection: str) -> int:
    if not exists(collection):
        return 0
    return int(_call(client().count, collection, exact=True).count)


def delete_collection(collection: str) -> None:
    if exists(collection):
        _call(client().delete_collection, collection)


def replace_page(collection: str, url: str, points: list) -> None:
    """Neue Chunks upserten, danach veraltete Chunks derselben URL entfernen."""
    for start in range(0, len(points), 64):
        _call(client().upsert, collection_name=collection, points=points[start:start + 64], wait=True)
    url_match = qm.FieldCondition(key="url", match=qm.MatchValue(value=url))
    keep = [p.id for p in points]
    flt = qm.Filter(must=[url_match], must_not=[qm.HasIdCondition(has_id=keep)]) if keep else qm.Filter(must=[url_match])
    _call(client().delete, collection_name=collection, points_selector=qm.FilterSelector(filter=flt), wait=True)


def search(collection: str, vector: list[float], limit: int, min_score: float) -> list[dict]:
    if not exists(collection):
        return []
    result = _call(
        client().query_points,
        collection_name=collection,
        query=vector,
        limit=limit,
        score_threshold=min_score,
        with_payload=True,
    )
    return [{"score": float(p.score), **(p.payload or {})} for p in result.points]
