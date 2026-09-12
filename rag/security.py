"""Защита от prompt-инъекций в проиндексированных документах.

Три слоя (Задание 5), каждый включается флагом в настройках:
1. ingest — пометка подозрительных чанков при индексации;
2. retrieve — отбрасывание помеченных и чистка остальных;
3. prompt — инструкция модели считать документы данными (см. rag/prompts.py).
"""

import re

from rag.config import get_settings

INJECTION_PATTERNS = (
    r"ignore\s+(all\s+|any\s+|previous\s+)?instructions?",
    r"disregard\s+(all\s+|any\s+|previous\s+)",
    r"forget\s+(all\s+|everything|your\s+instructions)",
    r"you\s+are\s+now\s+",
    r"system\s*(prompt|message)\s*:",
    r"\boutput\s*:",
    r"игнорируй\s+(все\s+|любые\s+|предыдущие\s+)?инструкц",
    r"забудь\s+(всё|все|свои\s+инструкц)",
    r"выведи\s+(системный|свой)\s+промпт",
    r"суперпароль",
    r"теперь\s+ты\s+",
)

_COMPILED = tuple(re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS)


def is_suspicious(text: str) -> bool:
    """Содержит ли текст признаки prompt-инъекции."""
    return any(pattern.search(text) for pattern in _COMPILED)


def sanitize(text: str) -> str:
    """Вырезает из текста императивные конструкции, оставляя факты."""
    result = text
    for pattern in _COMPILED:
        result = re.sub(
            rf"[^.!?]*{pattern.pattern}[^.!?]*[.!?]?",
            "",
            result,
            flags=re.IGNORECASE,
        )
    # Схлопываем осиротевшие пробелы
    return re.sub(r"\s{2,}", " ", result).strip()


def filter_chunks(chunks: list[dict]) -> list[dict]:
    """Отбрасывает чанки с признаками инъекции.

    Слой независим от ingest: проверяет текст заново, поэтому ловит и то,
    что не было помечено при индексации. Отключается флагом — это нужно,
    чтобы продемонстрировать утечку в Задании 5.
    """
    if not get_settings().security_retrieve_filter:
        return chunks

    safe = []
    for chunk in chunks:
        if is_suspicious(chunk["text"]):
            continue
        safe.append(chunk)

    return safe
