"""Настройки приложения, читаются из переменных окружения."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация RAG-бота.

    Все провайдеры (Infinity, OpenAI, DeepSeek, YandexGPT, Ollama)
    OpenAI-совместимы, поэтому переключение — это смена base_url и модели.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    embed_base_url: str = "http://localhost:7997"
    embed_api_key: str = "not-needed"
    embed_model: str = "deepvk/USER-bge-m3"
    embed_query_model: str = ""
    # Эмбеддер Яндекса принимает только один текст за запрос:
    # "Array input must contain exactly one string"
    embed_supports_batch: bool = True
    embed_dim: int = 1024
    # Префиксы инструктированных моделей (USER-bge-m3, e5). Для облачных
    # эмбеддингов OpenAI их быть не должно — очистите обе переменные
    embed_query_prefix: str = "query: "
    embed_passage_prefix: str = "passage: "

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # Для YandexGPT: идентификатор каталога, уходит
    # заголовком OpenAI-Project при вызове API
    yandex_folder_id: str = ""

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "knowledge_base"

    top_k: int = 5
    score_threshold: float = 0.45

    security_ingest_filter: bool = True
    security_retrieve_filter: bool = True
    security_prompt_guard: bool = True


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек."""
    return Settings()
