"""Подмена терминов исходной вселенной на вымышленные.

Цель — получить базу знаний, которой LLM гарантированно не видела
при обучении: только так проверяется, что бот отвечает из индекса,
а не по памяти.
"""

import argparse
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
TERMS_FILE = ROOT / "data" / "terms_map.json"


def apply_terms_map(text: str, terms: dict[str, str]) -> str:
    """Заменяет все вхождения терминов в тексте.

    Длинные термины идут первыми, иначе составное имя развалится
    на уже заменённые куски. Граница слова защищает от совпадений
    внутри других слов, захваченное окончание сохраняет падеж.

    Замена делается ОДНИМ проходом по общему regex с alternation,
    а не последовательными проходами по каждому термину. Это важно:
    если термин "X" заменяется на "Y-X" (например, "Тич" -> "Тич-Гриф"),
    отдельный проход по короткому ключу "Тич" после этого находит "Тич"
    внутри уже подставленного "Тич-Гриф" и снова его заменяет — получается
    "Тич-Гриф-Гриф". Аналогично короткий ключ "Пираты" разъедает изнутри
    уже готовую составную замену "Пираты Роджера" -> "Пираты Рогана".
    Единый проход исключает повторную обработку подставленного текста.
    """
    ordered = sorted(terms.items(), key=lambda item: len(item[0]), reverse=True)

    # lower_map — запасной вариант для регистронезависимого совпадения
    # ("гранд лайн" в середине предложения при ключе "Гранд Лайн")
    exact_map = dict(ordered)
    lower_map: dict[str, str] = {}
    for source, replacement in ordered:
        lower_map.setdefault(source.lower(), replacement)

    # ([а-яё]{0,3}) — падежное окончание, переносим его в замену
    alternation = "|".join(re.escape(source) for source, _ in ordered)
    pattern = re.compile(
        r"\b(" + alternation + r")([а-яё]{0,3})\b",
        re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        matched, suffix = match.group(1), match.group(2)
        replacement = exact_map.get(matched, lower_map[matched.lower()])
        return replacement + suffix

    return pattern.sub(replace, text)


def load_terms() -> dict[str, str]:
    """Читает словарь замен."""
    return json.loads(TERMS_FILE.read_text(encoding="utf-8"))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Подмена терминов в корпусе")
    parser.add_argument("--src", default="tmp/clean", help="Каталог с очищенными текстами")
    parser.add_argument("--out", default="knowledge_base", help="Каталог базы знаний")
    args = parser.parse_args()

    terms = load_terms()
    src_dir = ROOT / args.src
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for path in sorted(src_dir.glob("*.md")):
        text = apply_terms_map(path.read_text(encoding="utf-8"), terms)
        new_name = apply_terms_map(path.stem, terms)
        (out_dir / f"{new_name}.md").write_text(text, encoding="utf-8")
        count += 1

    print(f"Обработано документов: {count} -> {out_dir}")
    print(f"Терминов в словаре: {len(terms)}")


if __name__ == "__main__":
    main()
