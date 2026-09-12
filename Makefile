.PHONY: sync test lint corpus kb index snapshot restore api demo up down

sync:
	uv sync

# Гоняет весь набор тестов разом; при отладке падающего теста
# запускайте его отдельно: uv run pytest -v tests/test_x.py::test_y
test:
	uv run pytest -v

lint:
	uv run ruff check . && uv run ty check

corpus:
	uv run python scripts/fetch_corpus.py --out tmp/clean

kb:
	uv run python scripts/anonymize.py --src tmp/clean --out knowledge_base

index:
	uv run python scripts/build_index.py --recreate

api:
	uv run python -m rag.api


demo:
	uv run python scripts/demo_run.py

up:
	docker compose up -d

down:
	docker compose down

snapshot:
	curl -s -X POST http://localhost:6333/collections/knowledge_base/snapshots > /dev/null
	curl -s -o data/snapshots/knowledge_base.snapshot \
		"http://localhost:6333/collections/knowledge_base/snapshots/$$(curl -s http://localhost:6333/collections/knowledge_base/snapshots | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"][-1]["name"])')"
	@ls -lh data/snapshots/knowledge_base.snapshot

restore:
	curl -s -X POST http://localhost:6333/collections/knowledge_base/snapshots/upload \
		-H 'Content-Type: multipart/form-data' \
		-F 'snapshot=@data/snapshots/knowledge_base.snapshot'
	@curl -s http://localhost:6333/collections/knowledge_base | python3 -c 'import sys,json;print("точек:",json.load(sys.stdin)["result"]["points_count"])'
