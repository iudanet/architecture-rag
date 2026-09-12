"""Тесты подмены терминов."""

from scripts.anonymize import apply_terms_map


def test_replaces_longest_terms_first():
    """Составной термин не должен распасться на части."""
    terms = {"Монки Д. Луффи": "Кайро Д. Вельт", "Луффи": "Вельт"}

    result = apply_terms_map("Монки Д. Луффи — капитан. Луффи смеётся.", terms)

    assert result == "Кайро Д. Вельт — капитан. Вельт смеётся."


def test_replaces_case_insensitive_inside_sentence():
    terms = {"Гранд Лайн": "Великий Разлом"}

    result = apply_terms_map("Путь через гранд лайн опасен.", terms)

    assert "Великий Разлом" in result
    assert "гранд лайн" not in result.lower()


def test_leaves_unrelated_text_untouched():
    terms = {"Нами": "Сайра"}

    result = apply_terms_map("Корабль вышел в море.", terms)

    assert result == "Корабль вышел в море."


def test_is_deterministic():
    terms = {"Зоро": "Крайн"}
    text = "Зоро тренируется. Зоро спит."

    assert apply_terms_map(text, terms) == apply_terms_map(text, terms)


def test_no_source_terms_remain():
    """Ключевое требование ТЗ: исходные термины не должны остаться."""
    terms = {"Дьявольский фрукт": "Плод Бездны", "Дозор": "Легион"}
    text = "Дьявольский фрукт даёт силу. Дозор преследует пиратов."

    result = apply_terms_map(text, terms)

    assert "Дьявольский" not in result
    assert "Дозор" not in result


def test_does_not_replace_term_inside_another_word():
    """Термин на границе слова не должен матчиться внутри чужого слова.

    «Нами» не должен захватываться внутри «наминает» — граница слова
    защищает от таких ложных совпадений.
    """
    terms = {"Нами": "Сайра"}

    result = apply_terms_map("Нами наминает", terms)

    assert result == "Сайра наминает"
    assert "наминает" in result
