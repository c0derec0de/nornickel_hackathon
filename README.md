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

## LLM — компактная открытая модель `qwen2.5:3b-instruct`

Извлечение сущностей и ответы работают на **компактной открытой 3B-модели**
`qwen2.5:3b-instruct` (~1.9 ГБ): сильный RU/EN, держит structured JSON. Осознанно берём 3B —
экономия ресурсов при сохранении точности (критерий оргов). Провайдер переключается одной
переменной `LLM_PROVIDER` (см. `.env.example`):

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
   - Проверка LLM: `curl http://localhost:8010/health`

3. Проиндексируй корпус (данные в `backend/data/corpus/`, рекурсивно, форматы pdf/docx/pptx):
   ```bash
   # фоново, возобновляемо; следи за прогрессом
   curl -X POST "http://localhost:8010/ingest?reset=true"
   curl http://localhost:8010/ingest/status
   ```

4. Открой http://localhost:5273 и задавай вопросы (граф достраивается по мере ингеста).

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
