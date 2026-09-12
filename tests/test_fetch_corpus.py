"""Тесты чистки wikitext."""

from scripts.fetch_corpus import clean_wikitext


def test_removes_templates_and_infobox():
    raw = "{{Simple Box\n| image = x.png\n}}\n'''Гранд Лайн''' — маршрут.{{Qref|chap=101}}"

    result = clean_wikitext(raw)

    assert "Simple Box" not in result
    assert "Qref" not in result
    assert "Гранд Лайн — маршрут." in result


def test_unwraps_links_keeping_visible_text():
    raw = "Основатель [[Пираты Соломенной Шляпы|команды]] и [[капитан]]."

    result = clean_wikitext(raw)

    assert result == "Основатель команды и капитан."


def test_drops_service_sections():
    raw = "Основной текст.\n\n== Ссылки ==\n* [http://x.com сайт]\n\n== Навигация ==\nшаблон"

    result = clean_wikitext(raw)

    assert "Основной текст." in result
    assert "Навигация" not in result
    assert "Ссылки" not in result


def test_removes_interwiki_links_but_keeps_normal_colon_text():
    """Межъязыковые ссылки (en:Grand Line) убираются, а обычный текст
    с двоеточием внутри предложения — нет."""
    raw = "Основной текст.\n\nen:Grand Line\nes:Grand Line\nzh-tw:Grand Line\n\nПравило: текст."

    result = clean_wikitext(raw)

    assert "Основной текст." in result
    assert "Grand Line" not in result
    assert "en:" not in result
    assert "es:" not in result
    assert "zh-tw:" not in result
    assert "Правило: текст." in result
