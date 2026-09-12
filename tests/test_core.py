"""Тесты слоя эмбеддингов и поиска."""

from rag import core


class _FakeEmbeddings:
    """Фейковый клиент эмбеддингов: запоминает, что ему передали."""

    def __init__(self):
        self.last_input: list[str] | None = None

    def create(self, model: str, input: list[str], **kwargs):
        self.last_input = input

        class _Item:
            embedding = [0.1] * 1024

        class _Response:
            data = [_Item()]

        return _Response()


def test_embed_adds_passage_prefix_for_documents(monkeypatch):
    fake = _FakeEmbeddings()
    monkeypatch.setattr(core, "_embed_client", lambda: type("C", (), {"embeddings": fake})())

    core.embed("Великий Разлом опасен", is_query=False)

    assert fake.last_input == ["passage: Великий Разлом опасен"]


def test_embed_adds_query_prefix_for_queries(monkeypatch):
    fake = _FakeEmbeddings()
    monkeypatch.setattr(core, "_embed_client", lambda: type("C", (), {"embeddings": fake})())

    core.embed("Кто капитан?", is_query=True)

    assert fake.last_input == ["query: Кто капитан?"]


def test_embed_rejects_wrong_dimension(monkeypatch):
    class _BadEmbeddings:
        def create(self, model: str, input: list[str], **kwargs):
            class _Item:
                embedding = [0.1] * 10

            class _Response:
                data = [_Item()]

            return _Response()

    monkeypatch.setattr(
        core, "_embed_client", lambda: type("C", (), {"embeddings": _BadEmbeddings()})()
    )

    try:
        core.embed("текст")
    except ValueError as exc:
        assert "размерност" in str(exc).lower()
    else:
        raise AssertionError("Ожидалась ValueError при неверной размерности")
