.PHONY: up down logs health ingest ingest-full status test rebuild

# Поднять весь стек (neo4j + chroma + ollama + backend + frontend)
up:
	docker compose up -d --build
	@echo "UI: http://localhost:5273 | API: http://localhost:8010/docs"
	@echo "Дождись модели: make health (нужно model_pulled: true)"

# Остановить и удалить контейнеры
down:
	docker compose down

# Полная пересборка (без кэша)
rebuild:
	docker compose build --no-cache
	docker compose up -d

logs:
	docker compose logs -f backend

# Проверка готовности LLM (ждём model_pulled: true)
health:
	curl -s http://localhost:8010/health | python3 -m json.tool

# Индексация. Если корпус пуст — берётся демо-сид автоматически.
ingest:
	curl -s -X POST "http://localhost:8010/ingest?reset=true" | python3 -m json.tool

# Полный корпус, по 6 чанков на документ
ingest-full:
	curl -s -X POST "http://localhost:8010/ingest?reset=true&max_chunks_per_doc=6" | python3 -m json.tool

status:
	curl -s http://localhost:8010/ingest/status | python3 -m json.tool

# Юнит-тесты чистой логики (нужны зависимости backend)
test:
	cd backend && PYTHONPATH=. python tests/test_logic.py && PYTHONPATH=. python tests/test_llm_backoff.py
