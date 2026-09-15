"""Тесты сборки промпта."""

from rag.prompts import NO_ANSWER, SYSTEM_PROMPT, build_messages


def test_system_prompt_requires_step_by_step_reasoning():
    """Chain-of-Thought: модель должна показывать шаги."""
    assert "шаг" in SYSTEM_PROMPT.lower()


def test_system_prompt_forbids_following_document_instructions():
    """Третий слой защиты: документы — данные, а не инструкции."""
    lowered = SYSTEM_PROMPT.lower()
    assert "инструкц" in lowered
    assert "данные" in lowered or "данными" in lowered


def test_messages_include_few_shot_example():
    messages = build_messages("Кто капитан?", [])

    roles = [m["role"] for m in messages]
    # system + минимум одна пара примера + вопрос пользователя
    assert roles[0] == "system"
    assert roles.count("assistant") >= 1
    assert roles[-1] == "user"


def test_context_chunks_are_embedded_in_user_message():
    chunks = [
        {"text": "Вельт — капитан флота.", "score": 0.9, "source": "a.md", "title": "Вельт"}
    ]

    messages = build_messages("Кто капитан?", chunks)

    assert "Вельт — капитан флота." in messages[-1]["content"]
    assert "a.md" in messages[-1]["content"]


def test_empty_context_asks_for_honest_refusal():
    messages = build_messages("Кто капитан?", [])

    assert NO_ANSWER in messages[-1]["content"]
