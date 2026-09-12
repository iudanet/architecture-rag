"""Тесты HTTP-контракта."""

from fastapi.testclient import TestClient

from rag import api


def _client(monkeypatch, result: dict) -> TestClient:
    monkeypatch.setattr(api, "answer", lambda question: result)
    return TestClient(api.app)


def test_health_returns_ok():
    client = TestClient(api.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_returns_answer_with_sources(monkeypatch):
    client = _client(
        monkeypatch,
        {
            "answer": "Капитан — Вельт.",
            "sources": ["velt.md"],
            "citations": [],
            "chunks_used": 1,
            "max_score": 0.9,
        },
    )

    response = client.post("/ask", json={"question": "Кто капитан?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Капитан — Вельт."
    assert body["sources"] == ["velt.md"]


def test_ask_rejects_empty_question():
    client = TestClient(api.app)

    response = client.post("/ask", json={"question": "   "})

    assert response.status_code == 422


def test_ask_requires_question_field():
    client = TestClient(api.app)

    response = client.post("/ask", json={})

    assert response.status_code == 422


def test_ask_returns_nonempty_citations(monkeypatch):
    """Ответ обязан нести цитаты с источником, скором, сниппетом и ссылкой."""
    client = _client(
        monkeypatch,
        {
            "answer": "Капитан — Вельт.",
            "sources": ["Кайро Д. Вельт.md"],
            "citations": [
                {
                    "source": "Кайро Д. Вельт.md",
                    "title": "Кайро Д. Вельт",
                    "score": 0.87,
                    "chunk_id": 0,
                    "snippet": "Кайро Д. Вельт — капитан Вольного Флота Пепельного Стяга.",
                    "url": "/kb/%D0%9A%D0%B0%D0%B9%D1%80%D0%BE%20%D0%94.%20%D0%92%D0%B5%D0%BB%D1%82.md",
                }
            ],
            "chunks_used": 1,
            "max_score": 0.87,
        },
    )

    response = client.post("/ask", json={"question": "Кто капитан?"})

    assert response.status_code == 200
    citations = response.json()["citations"]
    assert citations, "citations не должны быть пустыми"
    citation = citations[0]
    assert citation["source"] == "Кайро Д. Вельт.md"
    assert citation["score"] == 0.87
    assert "капитан" in citation["snippet"]
    assert citation["url"].startswith("/kb/")


def test_read_doc_returns_existing_document():
    """Реальный документ базы знаний должен отдаваться как текст."""
    client = TestClient(api.app)

    response = client.get("/kb/Великий Разлом.md")

    assert response.status_code == 200
    assert response.text.strip() != ""


def test_read_doc_returns_404_for_missing_document():
    client = TestClient(api.app)

    response = client.get("/kb/несуществующий-файл.md")

    assert response.status_code == 404


def test_read_doc_blocks_path_traversal():
    """Попытка выйти за пределы knowledge_base не должна отдавать файл.

    StaticFiles в зависимости от версии starlette может ответить 404,
    403 или 400 — код не фиксируем, важно, что это не 200 и что
    в ответе нет содержимого системного файла.
    """
    client = TestClient(api.app)

    response = client.get("/kb/..%2F..%2Fetc%2Fpasswd")

    assert response.status_code != 200
    assert "root:" not in response.text


def test_read_doc_blocks_path_traversal_encoded_dots():
    """Второй вариант path traversal — с ведущим слэшем после кодирования."""
    client = TestClient(api.app)

    response = client.get("/kb/%2e%2e%2f%2e%2e%2fetc%2fpasswd")

    assert response.status_code != 200
    assert "root:" not in response.text


def test_swagger_ui_is_not_shadowed_by_kb_route():
    """/docs обязан остаться встроенным Swagger UI, а не нашим маршрутом."""
    client = TestClient(api.app)

    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_index_page_renders_with_static_links():
    """Главная страница — шаблон Jinja2, подключающий стили и скрипт из /static."""
    client = TestClient(api.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "/static/style.css" in response.text
    assert "/static/app.js" in response.text


def test_static_style_is_served():
    client = TestClient(api.app)

    response = client.get("/static/style.css")

    assert response.status_code == 200


def test_static_script_is_served():
    client = TestClient(api.app)

    response = client.get("/static/app.js")

    assert response.status_code == 200
