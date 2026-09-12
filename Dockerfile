FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Сначала зависимости — слой кэшируется между сборками, пока не меняется lock-файл
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Код проекта: rag/ (включая templates и static для web-интерфейса),
# скрипты индексации, база знаний и вспомогательные данные (термины, справочник страниц)
COPY rag/ ./rag/
COPY scripts/ ./scripts/
COPY knowledge_base/ ./knowledge_base/
COPY data/ ./data/

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "rag.api", "--host", "0.0.0.0", "--port", "8000"]
