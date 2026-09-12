"""Эмбеддинги и векторный поиск.

Эмбеддинги считает локальный Infinity через OpenAI-совместимый API —
тот же протокол, что у облачных провайдеров, поэтому клиент один.
"""

import logging
from functools import lru_cache

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from rag.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _embed_client() -> OpenAI:
    """Клиент сервиса эмбеддингов."""
    settings = get_settings()
    return OpenAI(base_url=settings.embed_base_url, api_key=settings.embed_api_key)


@lru_cache
def get_qdrant() -> QdrantClient:
    """Клиент векторной базы."""
    settings = get_settings()
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def embed(text: str, is_query: bool = False) -> list[float]:
    """Считает эмбеддинг текста.

    USER-bge-m3 обучена на инструктированных префиксах: документы
    кодируются как "passage: ", запросы — как "query: ".
    """
    return embed_batch([text], is_query=is_query)[0]


def embed_batch(texts: list[str], is_query: bool = False) -> list[list[float]]:
    """Считает эмбеддинги пачкой за один запрос.

    Батч радикально быстрее поштучных вызовов: накладные расходы на
    HTTP и прогон модели делятся на всю пачку.
    """
    settings = get_settings()
    prefix = settings.embed_query_prefix if is_query else settings.embed_passage_prefix
    model = settings.embed_query_model if is_query and settings.embed_query_model else settings.embed_model
    payload = [prefix + text for text in texts]

    # encoding_format=float обязателен: клиент openai по умолчанию просит base64,
    # который эмбеддер Яндекса не поддерживает
    if settings.embed_supports_batch:
        response = _embed_client().embeddings.create(
            model=model, input=payload, encoding_format="float"
        )
        vectors = [item.embedding for item in response.data]
    else:
        # Провайдер принимает только один текст за запрос — шлём по одному
        vectors = [
            _embed_client()
            .embeddings.create(model=model, input=[item], encoding_format="float")
            .data[0]
            .embedding
            for item in payload
        ]
    for vector in vectors:
        if len(vector) != settings.embed_dim:
            raise ValueError(
                f"Неверная размерность эмбеддинга: {len(vector)}, ожидалась {settings.embed_dim}"
            )

    return vectors


def search(query: str, top_k: int | None = None) -> list[dict]:
    """Ищет релевантные чанки в векторной базе."""
    settings = get_settings()
    limit = top_k or settings.top_k

    hits = get_qdrant().query_points(
        collection_name=settings.qdrant_collection,
        query=embed(query, is_query=True),
        limit=limit,
        # Слой ingest: помеченные при индексации чанки не выходят из базы
        query_filter=(
            Filter(must_not=[FieldCondition(key="suspicious", match=MatchValue(value=True))])
            if settings.security_ingest_filter
            else None
        ),
    )

    results = []
    for hit in hits.points:
        # Qdrant возвращает payload=None, если точка сохранена без метаданных
        payload = hit.payload or {}
        results.append(
            {
                "text": payload.get("text", ""),
                "score": hit.score,
                "source": payload.get("source", ""),
                "title": payload.get("title", ""),
                "chunk_id": payload.get("chunk_id", 0),
                "position": payload.get("position", 0),
                "suspicious": payload.get("suspicious", False),
            }
        )

    return results
