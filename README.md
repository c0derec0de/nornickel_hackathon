# SciGraph — R&D карта знаний (горно-металлургия)

Умный помощник для исследователей: **граф знаний (Neo4j) + семантический поиск (Chroma)**,
оркестрируемый **локальной опенсорс-LLM (Ollama · qwen2.5)**. Отвечает на сложные многопараметрические запросы по
материалам, процессам, экспериментам и оборудованию — с цитатами источников, подсветкой
**пробелов в знаниях** и **противоречий** между источниками.

Слева — чат на естественном языке (RU/EN), справа — интерактивный граф связей.

## Архитектура

См. [ARCHITECTURE.md](ARCHITECTURE.md).

```
Frontend (React) ─► Backend (FastAPI) ─► Neo4j (граф) + Chroma (вектора)
                         └─► Ollama · qwen2.5 (извлечение сущностей + генерация ответов)
```

## LLM — открытая модель Qwen3 (квантованная)

Извлечение сущностей и ответы работают на **открытой модели `qwen3:4b`**
(Q4 ~2.5 ГБ, нужно ~5-6 ГБ RAM): свежий Qwen3, сильный RU/EN, держит structured JSON.
Режим «thinking» отключается автоматически (`/no_think` + зачистка `<think>`). Модель — это
просто строка `LLM_MODEL`, легко сменить под железо: точнее — `qwen2.5:14b-instruct` (~9 ГБ) или
`qwen3:8b` (~5 ГБ); слабее — `qwen3:1.7b`. Провайдер переключается `LLM_PROVIDER` (см. `.env.example`):

**A) Ollama как сервис в docker-compose (по умолчанию)** — ничего ставить не надо:
`docker compose up` сам поднимет контейнер `ollama` и **автоматически скачает модель**
(сервис `ollama-pull`). Данные не покидают контур.
- На **Linux + NVIDIA**: раскомментируй блок `deploy` у сервиса `ollama` в compose → GPU.
- На **Mac**: контейнерный Ollama идёт на CPU. Для скорости (Metal) — host-Ollama:
  ```bash
  brew services start ollama && ollama pull qwen2.5:3b-instruct
  # в .env: OLLAMA_HOST=http://host.docker.internal:11434
  docker compose up -d --scale ollama=0 --scale ollama-pull=0
  ```

**B) OpenRouter** — OpenAI-совместимый, разрешён в РФ (но бесплатные `:free` часто дают 429):
```bash
# в .env: LLM_PROVIDER=openai, LLM_MODEL=qwen/qwen3-next-80b-a3b-instruct:free,
#         OPENAI_API_KEY=sk-or-...  (ключ с https://openrouter.ai/keys)
```

Эмбеддинги — опенсорс `multilingual-e5-large` через **fastembed** (ONNX, без torch), локально.

## Быстрый старт

1. Конфиг (ключи не нужны для Ollama):
   ```bash
   cp .env.example .env
   ```

2. Подними стек:
   ```bash
   docker compose up -d --build
   ```
   - Frontend: http://localhost:5273
   - Backend API: http://localhost:8010/docs
   - Neo4j Browser: http://localhost:7474 (neo4j / scigraph123)

3. **Дождись скачивания модели** (при первом старте `ollama-pull` тянет ~2.5 ГБ).
   Готовность — когда в ответе `"model_pulled": true`:
   ```bash
   curl http://localhost:8010/health
   ```

4. Проиндексируй данные (фоново, возобновляемо). Если корпус ещё не скачан —
   автоматически берётся демо-сид (4 документа), и приложение сразу рабочее:
   ```bash
   curl -X POST "http://localhost:8010/ingest?reset=true"
   curl http://localhost:8010/ingest/status      # прогресс / ETA
   ```

5. Открой http://localhost:5273 и задавай вопросы (граф достраивается по мере ингеста).

> Быстрее через `make`: `make up` → `make health` → `make ingest` → `make status`. Тесты: `make test`.

## Работа с полным корпусом (1453 файла)

Семантический поиск покрывает **весь корпус** сразу (эмбеддинги дёшевы). Граф извлекается
локальной моделью — это долго, поэтому ингест **фоновый и возобновляемый**, с лимитом чанков
на документ (`max_chunks_per_doc`, по умолчанию 6) для широкого покрытия всех документов.

```bash
# весь корпус, по 6 чанков на документ (широкое покрытие)
curl -X POST "http://localhost:8010/ingest?reset=true&max_chunks_per_doc=6"

# только по темам (быстрое демо)
curl -X POST "http://localhost:8010/ingest?name_filter=католит,МПГ,штейн,обессолив,шахтн"

# статус / ETA
curl http://localhost:8010/ingest/status
```
Прервали / упал контейнер — просто запусти `POST /ingest` снова (без `reset`): уже обработанные
чанки пропускаются.

## API

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/ingest?reset=bool` | Импорт корпуса → граф + вектора |
| POST | `/query` | NL-запрос → ответ + подграф + пробелы + противоречия |
| GET  | `/graph?entity=&depth=` | Подграф вокруг сущности |
| GET  | `/stats` | Статистика графа и векторов |
| GET  | `/health` | Проверка живости |

## Тесты

Юнит-тесты чистой логики (без БД/LLM/сети) — онтология, чанкинг, парсинг docx,
схемы извлечения, backoff-ретраи провайдера:
```bash
cd backend
PYTHONPATH=. python tests/test_logic.py
PYTHONPATH=. python tests/test_llm_backoff.py
```

## Демо-сценарии (сид-корпус)

1. Обессоливание воды при сульфатах 200–300 мг/л, сухой остаток ≤1000 мг/дм³.
2. Оптимальная скорость циркуляции католита (РФ 8–12 л/мин **vs** мир 15–20 л/мин → противоречие).
3. Распределение Au/Ag/МПГ между штейном и шлаком.
