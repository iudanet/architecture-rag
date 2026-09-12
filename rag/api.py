"""HTTP-интерфейс бота и консольный режим."""

import argparse
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from rag.pipeline import answer

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(title="RAG-бот по базе знаний", version="0.1.0")


class AskRequest(BaseModel):
    """Запрос пользователя."""

    question: str = Field(max_length=2000)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Вопрос не может быть пустым")
        return value.strip()


class AskResponse(BaseModel):
    """Ответ бота с диагностикой поиска."""

    answer: str
    sources: list[str]
    citations: list[dict]
    chunks_used: int
    max_score: float


@app.get("/health")
def health() -> dict:
    """Проверка живости сервиса."""
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict:
    """Отвечает на вопрос по базе знаний."""
    logger.info("Вопрос: %s", request.question)
    try:
        return answer(request.question)
    except Exception as exc:
        # Недоступны Qdrant, сервис эмбеддингов или LLM
        logger.exception("Ошибка обработки вопроса")
        raise HTTPException(
            status_code=503,
            detail=f"Сервис временно недоступен: {type(exc).__name__}",
        ) from exc


@app.get("/")
def index(request: Request) -> HTMLResponse:
    """Отдаёт страницу чата."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "RAG-бот по базе знаний"},
    )


# StaticFiles вместо самописного обработчика: защита от path traversal
# уже реализована и оттестирована в Starlette. Каталог назван `/kb/...`,
# а не `/docs/...`, чтобы не перекрывать встроенный Swagger UI (`/docs`).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/kb", StaticFiles(directory=KB_DIR), name="kb")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="RAG-бот")
    parser.add_argument("--host", default="0.0.0.0", help="Адрес HTTP-сервера")
    parser.add_argument("--port", type=int, default=8000, help="Порт HTTP-сервера")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
