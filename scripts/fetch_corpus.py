"""Выкачка статей из русской вики One Piece и очистка wikitext.

Fandom не отдаёт prop=extracts, поэтому берём сырой wikitext
через action=parse и чистим разметку регулярками.
"""

import argparse
import logging
import re
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://onepiece.fandom.com/ru/api.php"
CACHE_DIR = Path(__file__).resolve().parent.parent / "tmp" / "raw_cache"
PAGES_FILE = Path(__file__).resolve().parent.parent / "data" / "pages.txt"

SERVICE_SECTIONS = (
    "Ссылки",
    "Навигация",
    "Примечания",
    "Источники",
    "Галерея",
    "См. также",
)


def _strip_templates(text: str) -> str:
    """Удаляет {{...}} с учётом вложенности."""
    result = []
    depth = 0
    i = 0
    while i < len(text):
        if text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i) and depth:
            depth -= 1
            i += 2
        else:
            if not depth:
                result.append(text[i])
            i += 1
    return "".join(result)


def clean_wikitext(raw: str, title: str = "") -> str:
    """Превращает сырой wikitext в читаемый текст.

    title — заголовок статьи; если после очистки текст начинается с тире
    (жирное название статьи было внутри удалённого инфобокса), подставляем
    заголовок в начало, чтобы не терять подлежащее в первом предложении.
    """
    text = _strip_templates(raw)

    text = re.sub(r"\{\|.*?\|\}", "", text, flags=re.DOTALL)
    text = re.sub(r"\[\[(?:Файл|File|Категория|Category):[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\]", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^>]*?/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"'{2,5}", "", text)

    for name in SERVICE_SECTIONS:
        text = re.sub(rf"\n=+\s*{re.escape(name)}\s*=+.*?(?=\n=|\Z)", "", text, flags=re.DOTALL)

    text = re.sub(r"\n=+\s*(.*?)\s*=+", r"\n\1", text)
    text = re.sub(r"(?m)^[*#:;]+\s*", "", text)
    # Убираем межъязыковые ссылки (en:Grand Line) до схлопывания пустых
    # строк, иначе после них останутся дыры
    text = re.sub(r"(?m)^[a-z]{2,3}(?:-[a-z]+)?:.*$\n?", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    text = text.strip()

    if title and re.match(r"^[\-—]", text):
        text = f"{title} {text}"

    return text


def fetch_page(title: str, client: httpx.Client | None = None) -> str:
    """Скачивает wikitext одной статьи. Результат кэшируется на диск."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{title.replace('/', '_')}.txt"

    if cache_file.exists():
        logger.info("Из кэша: %s", title)
        return cache_file.read_text(encoding="utf-8")

    own_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(
            API_URL,
            params={
                "action": "parse",
                "page": title,
                "prop": "wikitext",
                "format": "json",
            },
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if own_client:
            client.close()

    if "error" in payload:
        raise ValueError(f"Статья не найдена: {title} ({payload['error'].get('code')})")

    raw = payload["parse"]["wikitext"]["*"]
    cache_file.write_text(raw, encoding="utf-8")
    logger.info("Скачано: %s (%d символов)", title, len(raw))
    return raw


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Выкачка корпуса из вики One Piece")
    parser.add_argument("--out", default="tmp/clean", help="Каталог для очищенных текстов")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    titles = [
        line.strip()
        for line in PAGES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    with httpx.Client(timeout=30) as client:
        for title in titles:
            try:
                raw = fetch_page(title, client=client)
            except (ValueError, httpx.HTTPError) as exc:
                logger.error("Пропуск %s: %s", title, exc)
                continue

            text = clean_wikitext(raw, title=title)
            (out_dir / f"{title.replace('/', '_')}.md").write_text(
                f"# {title}\n\n{text}\n", encoding="utf-8"
            )
            time.sleep(0.5)

    print(f"Готово. Очищенные тексты: {out_dir}")


if __name__ == "__main__":
    main()
