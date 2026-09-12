"""Тесты настроек приложения."""

from rag.config import Settings


def test_defaults_match_spec():
    """По умолчанию — Infinity с USER-bge-m3 и включённая защита."""
    settings = Settings(_env_file=None)

    assert settings.embed_model == "deepvk/USER-bge-m3"
    assert settings.embed_dim == 1024
    assert settings.top_k == 5
    assert settings.score_threshold == 0.45
    assert settings.security_ingest_filter is True
    assert settings.security_retrieve_filter is True
    assert settings.security_prompt_guard is True


def test_env_overrides_defaults(monkeypatch):
    """Переключение провайдера — только через env, без правок кода."""
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    monkeypatch.setenv("SECURITY_RETRIEVE_FILTER", "false")

    settings = Settings(_env_file=None)

    assert settings.llm_base_url == "https://api.deepseek.com/v1"
    assert settings.llm_model == "deepseek-chat"
    assert settings.security_retrieve_filter is False
