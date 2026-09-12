# RAG-бот по корпоративной базе знаний

Проектная работа 7 спринта. Бот отвечает на вопросы по базе знаний, честно
говорит «Я не знаю», когда ответа нет, и не выполняет команды, встреченные
внутри документов. Эмбеддинги считаются локально — документы не покидают
контур; LLM подключается через OpenAI-совместимый API, провайдер меняется
одной переменной окружения.

## Стек

| Слой | Решение |
|---|---|
| Векторная БД | Qdrant |
| Эмбеддинги | `deepvk/USER-bge-m3`, 1024-dim, локальный инференс через Infinity CPU |
| LLM | YandexGPT 5.1 (OpenAI-совместимый API) |
| Бэкенд | FastAPI + чат-окно + CLI |

## Соответствие заданиям

| Задание | Что сделано | Артефакт |
|---|---|---|
| 1. Исследование и выбор технологий | сравнение LLM, эмбеддингов, векторных БД, конфигурации сервера и вариантов развёртывания на реальных замерах | `docs/task1-research.md` |
| 2. Сбор и подготовка базы знаний | выгрузка 36 статей из вики, анонимизация терминов словарём (534 записи), защита от межвики-утечек | `scripts/fetch_corpus.py`, `scripts/anonymize.py`, `knowledge_base/` |
| 3. Построение векторного индекса | чанкинг, локальные эмбеддинги, загрузка в Qdrant с метаданными, переиндексация по одному документу | `scripts/build_index.py`, раздел «Что в индексе» ниже |
| 4. RAG-конвейер и API | поиск + Chain-of-Thought промпт + FastAPI/CLI | `rag/pipeline.py`, `rag/api.py`, `rag/prompts.py` |
| 5. Защита от prompt-инъекций | три независимых слоя защиты (ingest/retrieve/prompt), тест утечки в двух конфигурациях | `docs/task5-security.md`, `rag/security.py` |

## Быстрый старт

```bash
cp .env.example .env     # вписать LLM_API_KEY и YANDEX_FOLDER_ID
docker compose up -d
```

Чат — на http://localhost:8000

## Как выпустить ключ YandexGPT

Нужны **API-ключ сервисного аккаунта** (не протухает, в отличие от IAM-токена
с 12-часовым сроком) и **folder_id**.

### Через консоль

1. [console.yandex.cloud](https://console.yandex.cloud) → выбрать каталог,
   `folder_id` (вида `b1g...`) виден в адресной строке.
2. **Сервисные аккаунты** → *Создать*, имя `rag-bot`, роль `ai.languageModels.user`.
3. Аккаунт → *Создать новый ключ* → **API-ключ**, область
   `yc.ai.languageModels.execute`.
4. Скопировать секрет — показывается один раз.

### Через CLI

```bash
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
exec -l $SHELL
yc init --profile rag        # отдельный профиль, существующие не затрагиваются
FOLDER=$(yc config get folder-id)
yc iam service-account create --name rag-bot
SA_ID=$(yc iam service-account get --name rag-bot --format json | \
        python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
yc resource-manager folder add-access-binding "$FOLDER" \
    --role ai.languageModels.user --subject "serviceAccount:$SA_ID"
yc iam api-key create --service-account-id "$SA_ID" \
    --scopes yc.ai.languageModels.execute
```

Последняя команда печатает `secret` — это и есть ключ.

### Что вписать в .env

```bash
LLM_BASE_URL=https://ai.api.cloud.yandex.net/v1
LLM_MODEL=gpt://<folder_id>/yandexgpt-5.1
LLM_API_KEY=<секрет из api-key create>
YANDEX_FOLDER_ID=<folder_id>
```

`folder_id` указывается дважды: в имени модели и отдельной переменной —
она уходит заголовком `OpenAI-Project`, которого требует API Яндекса.

### Проверка

```bash
curl -s https://ai.api.cloud.yandex.net/v1/chat/completions \
  -H "Authorization: Bearer $LLM_API_KEY" -H "OpenAI-Project: $YANDEX_FOLDER_ID" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$LLM_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Ответь одним словом: столица Финляндии?\"}]}" \
  | python3 -m json.tool
```

Ожидаемый ответ — «Хельсинки» в `choices[0].message.content`.

## Другие провайдеры LLM

Меняются через `.env` без правок кода — все перечисленные API OpenAI-совместимы.

| Провайдер | `LLM_BASE_URL` | `LLM_MODEL` |
|---|---|---|
| **YandexGPT 5.1** (основной) | `https://ai.api.cloud.yandex.net/v1` | `gpt://<folder_id>/yandexgpt-5.1` |
| Qwen3-235B | тот же | `gpt://<folder_id>/qwen3-235b-a22b-fp8/latest` |
| GPT-OSS-120B | тот же | `gpt://<folder_id>/gpt-oss-120b/latest` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Ollama | `http://localhost:11434/v1` | `gemma4:e2b` |

Модели Yandex AI Studio переключаются одним именем модели, ключ и `folder_id`
остаются прежними.

## Что в индексе

| Параметр | Значение |
|---|---|
| Модель эмбеддингов | `deepvk/USER-bge-m3` (локально, Infinity) |
| Размерность вектора | 1024 |
| Документов | 37 (36 статей + 1 тестовый документ с инъекцией) |
| Чанков / точек в Qdrant | 419 |
| Время индексации, локальный эмбеддер | 2094.7 с (35 мин) |
| Время индексации, эмбеддер Яндекса (`text-embeddings`, 1536-dim) | 158.1 с (2.6 мин) |
| Порог релевантности (`SCORE_THRESHOLD`) | 0.45, подобран по распределению score на контрольных вопросах |

Полное сравнение вариантов — `docs/task1-research.md`.

## Пример запроса

| Параметр | Значение |
|---|---|
| Вопрос | «Кто капитан Вольного Флота Пепельного Стяга?» |
| Ответ | Кайро Д. Вельт (источник: `Кайро Д. Вельт.md`) |
| Фрагментов найдено | 5, max score 0.537 |
| Время ответа | 4.36 с |

Полные логи, включая честные отказы и поведение при инъекции — `docs/demo/demo_log.md`.

## Переиндексация по одному документу

Полная пересборка (`make index`) — 35 минут на локальном эмбеддере. Правка
одного файла — точечный режим, 9 секунд:

```bash
uv run python scripts/build_index.py --only "Файл.md"
```

Id чанков детерминированы (`uuid5` от `source:chunk_id`) — повторный запуск
перезаписывает точки того же документа вместо дублирования; лишние чанки
от сократившегося документа удаляются (`drop_stale_chunks`).

## Снапшот индекса

Готовый индекс лежит в `data/snapshots/knowledge_base.snapshot` (7.6 МБ, 419 векторов).
Восстановление вместо полной переиндексации:

```bash
make restore      # поднять индекс из снапшота
make snapshot     # сохранить текущее состояние индекса
```

Полная переиндексация с нуля занимает 35 минут на локальном эмбеддере,
восстановление из снапшота — около секунды.

## Разработка

```bash
uv sync                  # окружение
make corpus              # выкачать статьи из вики (scripts/fetch_corpus.py)
make kb                  # подменить термины, собрать базу знаний (scripts/anonymize.py)
make index               # построить векторный индекс с нуля (build_index.py --recreate)
make api                 # запустить сервер
make cli                 # консольный режим
make demo                # демонстрационный прогон (scripts/demo_run.py)
make up / make down      # docker compose up -d / down
make test                # uv run pytest -v — весь набор тестов
make lint                # uv run ruff check . && uv run ty check
```
