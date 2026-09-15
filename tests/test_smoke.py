"""Проверка, что окружение собрано и пакет импортируется."""


def test_rag_package_importable():
    import rag

    assert rag is not None
