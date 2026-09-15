"""RAG-пайплайн: поиск -> фильтрация -> промпт -> генерация."""

import logging
from functools import lru_cache
from typing import cast
from urllib.parse import quote

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from rag.config import get_settings
from rag.core import search
from rag.prompts import NO_ANSWER, build_messages
from rag.security import filter_chunks, sanitize

logger = logging.getLogger(__name__)


@lru_cache
def _llm_client() -> OpenAI:
    """Клиент LLM. Все поддерживаемые провайдеры OpenAI-совместимы.

    YandexGPT дополнительно требует идентификатор каталога
    в заголовке OpenAI-Project.
    """
    settings = get_settings()
    headers = {}
    if settings.yandex_folder_id:
        headers["OpenAI-Project"] = settings.yandex_folder_id

    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "not-needed",
        default_headers=headers or None,
    )


def _call_llm(messages: list[dict]) -> str:
    """Отправляет сообщения в модель и возвращает текст ответа."""
    settings = get_settings()
    response = _llm_client().chat.completions.create(
        model=settings.llm_model,
        messages=cast(list[ChatCompletionMessageParam], messages),
        temperature=0.2,
    )
    if not response.choices:
        return ""
    return response.choices[0].message.content or ""


def answer(question: str) -> dict:
    """Отвечает на вопрос по базе знаний.

    Возвращает ответ, использованные источники и диагностику поиска.
    Если релевантных фрагментов нет — честно сообщает об этом,
    не обращаясь к модели.
    """
    settings = get_settings()
    chunks = search(question)
    max_score = max((chunk["score"] for chunk in chunks), default=0.0)

    relevant = [chunk for chunk in chunks if chunk["score"] >= settings.score_threshold]
    safe = filter_chunks(relevant)

    if not safe:
        logger.info("Ответ не найден: max_score=%.3f, вопрос=%r", max_score, question)
        return {
            "answer": NO_ANSWER,
            "sources": [],
            "citations": [],
            "chunks_used": 0,
            "max_score": max_score,
        }

    if settings.security_retrieve_filter:
        safe = [{**chunk, "text": sanitize(chunk["text"])} for chunk in safe]

    text = _call_llm(build_messages(question, safe))

    return {
        "answer": text,
        "sources": list(dict.fromkeys(chunk["source"] for chunk in safe)),
        "citations": [
            {
                "source": chunk["source"],
                "title": chunk.get("title", ""),
                "score": round(float(chunk["score"]), 3),
                "chunk_id": chunk.get("chunk_id", 0),
                "position": chunk.get("position", 0),
                "snippet": chunk["text"][:200],
                "url": f"/kb/{quote(chunk['source'])}",
            }
            for chunk in safe
        ],
        "chunks_used": len(safe),
        "max_score": max_score,
    }
