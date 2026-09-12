"""Построение векторного индекса базы знаний (Задание 3).

Разбивает документы на чанки, считает эмбеддинги и грузит в Qdrant
вместе с метаданными для цитирования.
"""

import argparse
import logging
import time
import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from rag.config import get_settings
from rag.core import embed_batch, get_qdrant
from rag.security import is_suspicious

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

# ~800 токенов на чанк; для русского это примерно 2400 символов
CHUNK_SIZE = 2400
CHUNK_OVERLAP = 300
EMBED_BATCH = 32


def chunk_uuid(chunk: dict) -> str:
    """Детерминированный идентификатор чанка.

    Выводится из источника и номера фрагмента, поэтому повторная
    индексация того же документа ПЕРЕЗАПИСЫВАЕТ его чанки, а не плодит
    дубликаты. Это и делает возможным обновление по одному документу.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{chunk['source']}:{chunk['chunk_id']}"))


def drop_stale_chunks(client, collection: str, source: str, kept: int) -> None:
    """Удаляет чанки документа, оставшиеся от прежней, более длинной версии.

    Если документ сократился, старые фрагменты с большими номерами
    остались бы в индексе и продолжали находиться поиском.
    """
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[
                FieldCondition(key="source", match=MatchValue(value=source)),
                FieldCondition(key="chunk_id", range=Range(gte=kept)),
            ]
        ),
    )


def split_documents(docs: list[dict]) -> list[dict]:
    """Режет документы на чанки, сохраняя источник и позицию."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    settings = get_settings()
    chunks: list[dict] = []

    for doc in docs:
        pieces = splitter.split_text(doc["text"])
        # Фактическое смещение фрагмента в документе: накапливать длины нельзя,
        # сплиттер оставляет перекрытие и вырезает разделители
        cursor = 0
        for chunk_id, piece in enumerate(pieces):
            position = doc["text"].find(piece, cursor)
            if position == -1:
                position = cursor
            cursor = position + 1
            suspicious = settings.security_ingest_filter and is_suspicious(piece)
            chunks.append(
                {
                    "text": piece,
                    "source": doc["source"],
                    "title": doc["title"],
                    "chunk_id": chunk_id,
                    "position": position,
                    "suspicious": suspicious,
                }
            )

    return chunks


def load_documents(kb_dir: Path) -> list[dict]:
    """Читает базу знаний с диска."""
    docs = []
    for path in sorted(kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else path.stem
        title = first_line.lstrip("# ").strip() or path.stem
        docs.append({"text": text, "source": path.name, "title": title})
    return docs


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Индексация базы знаний в Qdrant")
    parser.add_argument("--kb", default="knowledge_base", help="Каталог базы знаний")
    parser.add_argument("--recreate", action="store_true", help="Пересоздать коллекцию")
    parser.add_argument(
        "--collection",
        default=None,
        help="Имя коллекции; по умолчанию берётся из настроек. "
        "Позволяет держать рядом индексы разных эмбеддеров для сравнения",
    )
    parser.add_argument(
        "--only",
        default=None,
        metavar="ФАЙЛ",
        help="Переиндексировать только один документ базы знаний. "
        "Обновление идёт секунды вместо полного прогона",
    )
    args = parser.parse_args()

    settings = get_settings()
    collection = args.collection or settings.qdrant_collection
    client = get_qdrant()
    started = time.monotonic()

    docs = load_documents(ROOT / args.kb)
    if args.only:
        docs = [doc for doc in docs if doc["source"] == args.only]
        if not docs:
            raise SystemExit(f"Документ не найден в базе знаний: {args.only}")

    print(f"Документов: {len(docs)}")

    chunks = split_documents(docs)
    print(f"Чанков: {len(chunks)}")

    if args.recreate and client.collection_exists(collection):
        client.delete_collection(collection)

    if not client.collection_exists(collection):
        client.create_collection(
            collection,
            vectors_config=VectorParams(size=settings.embed_dim, distance=Distance.COSINE),
        )
        print(f"Коллекция создана: {collection}")

    # Каждая пачка сразу уходит в Qdrant: в памяти ничего не копится,
    # а при обрыве уже загруженное остаётся в базе
    loaded = 0
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        vectors = embed_batch([chunk["text"] for chunk in batch])

        client.upsert(
            collection_name=collection,
            points=[
                PointStruct(id=chunk_uuid(chunk), vector=vector, payload=chunk)
                for chunk, vector in zip(batch, vectors, strict=True)
            ],
        )

        loaded += len(batch)
        print(f"  загружено: {loaded}/{len(chunks)}", flush=True)

    if not args.recreate:
        per_source: dict[str, int] = {}
        for chunk in chunks:
            per_source[chunk["source"]] = per_source.get(chunk["source"], 0) + 1
        for source, kept in per_source.items():
            drop_stale_chunks(client, collection, source, kept)

    elapsed = time.monotonic() - started
    print(f"Загружено векторов: {loaded}")
    print(f"Время индексации: {elapsed:.1f} с")


if __name__ == "__main__":
    main()
