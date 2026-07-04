"""LLM-слой с провайдер-абстракцией.

По умолчанию — локальный **Ollama** (бесплатно, опенсорс, qwen2.5). Опционально — Anthropic.
Задачи: извлечение сущностей (structured JSON) и генерация ответов.
"""
import json
import re
import time
import httpx
from .config import settings
from .schemas import ExtractionResult
from .ontology import ENTITY_TYPES, RELATION_TYPES

# ---- JSON-схема извлечения (общая для Ollama format и Anthropic tool) ----
_NUM = {
    "type": "object",
    "properties": {
        "quantity": {"type": "string"},
        "op": {"type": "string", "enum": ["<=", ">=", "=", "range"]},
        "value": {"type": "number"},
        "value_max": {"type": "number"},
        "unit": {"type": "string"},
    },
    "required": ["quantity", "op", "value"],
}

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ENTITY_TYPES},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "type"],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "type": {"type": "string", "enum": RELATION_TYPES},
                    "condition": _NUM,
                },
                "required": ["source", "target", "type"],
            },
        },
        "constraints": {"type": "array", "items": _NUM},
        "geography": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["entities", "relations"],
}

EXTRACT_SYSTEM = (
    "Ты — экстрактор знаний для горно-металлургической R&D-базы. "
    "Из фрагмента научного/технического текста (RU или EN) извлеки сущности предметной "
    "области (материалы, процессы, оборудование, свойства, эксперименты, публикации, эксперты, "
    "установки, географию), связи между ними и ЧИСЛОВЫЕ ОГРАНИЧЕНИЯ (концентрации, температуры, "
    "скорости, производительность, экономику) с единицами измерения. "
    "Крайне важно точно передавать числа и единицы. Нормализуй синонимы к канону "
    "(electrowinning→электроэкстракция, ПВП→печь взвешенной плавки). "
    "Не выдумывай факты. Верни строго JSON по схеме."
)

ANSWER_SYSTEM = (
    "Ты — эксперт-аналитик R&D горно-металлургической отрасли. Отвечай ТОЛЬКО на основе "
    "предоставленного контекста (фрагменты источников + факты из графа знаний). "
    "Структурируй ответ: суть → детали с числами и единицами → источники. "
    "Обязательно указывай числовые значения и диапазоны. Если данных недостаточно — честно "
    "скажи об этом и укажи, каких данных не хватает. Различай отечественную и зарубежную практику. "
    "Отвечай на языке вопроса."
)


# ===================== Общее =====================

def _is_qwen3() -> bool:
    return "qwen3" in settings.llm_model.lower()


def _no_think(system: str) -> str:
    """Qwen3 по умолчанию «думает» (<think>...</think>) — глушим для любого провайдера."""
    return system + " /no_think" if _is_qwen3() else system


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ===================== Ollama =====================

def _ollama_chat(system: str, user: str, fmt: dict | None = None,
                 max_tokens: int = 2000) -> str:
    is_qwen3 = _is_qwen3()
    system = _no_think(system)
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": max_tokens},
    }
    if is_qwen3:
        payload["think"] = False
    if fmt:
        payload["format"] = fmt
    r = httpx.post(f"{settings.ollama_host}/api/chat", json=payload, timeout=300)
    r.raise_for_status()
    return _strip_think(r.json()["message"]["content"])


def _ollama_extract(chunk: str) -> ExtractionResult:
    raw = _ollama_chat(EXTRACT_SYSTEM, chunk, fmt=EXTRACT_SCHEMA)
    try:
        return ExtractionResult(**_extract_json(raw))
    except Exception:
        return ExtractionResult()


def _ollama_answer(question: str, context: str) -> str:
    return _ollama_chat(
        ANSWER_SYSTEM,
        f"ВОПРОС:\n{question}\n\nКОНТЕКСТ:\n{context}",
        max_tokens=1500,
    )


# ===================== OpenAI-совместимый (OpenRouter) =====================

def _openai_chat(system: str, user: str, json_mode: bool = False,
                 max_tokens: int = 2000, max_retries: int = 5) -> str:
    headers = {"Authorization": f"Bearer {settings.openai_api_key or 'not-needed'}",
               "Content-Type": "application/json",
               # необязательные заголовки OpenRouter для атрибуции
               "HTTP-Referer": "https://scigraph.local",
               "X-Title": "SciGraph"}
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _no_think(system)},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    # backoff на 429/5xx — free-tier OpenRouter часто rate-limit'ит
    delay = 3.0
    last_err = None
    for attempt in range(max_retries):
        r = httpx.post(f"{settings.openai_base_url}/chat/completions",
                       json=payload, headers=headers, timeout=180)
        if r.status_code == 200:
            data = r.json()
            if "choices" in data:
                return _strip_think(data["choices"][0]["message"]["content"])
            last_err = data.get("error")
        elif r.status_code in (429, 500, 502, 503):
            retry_after = None
            try:
                retry_after = r.json().get("error", {}).get("metadata", {}).get("retry_after_seconds")
            except Exception:
                pass
            time.sleep(retry_after or delay)
            delay = min(delay * 1.8, 30)
            last_err = f"HTTP {r.status_code}"
            continue
        else:
            r.raise_for_status()
    raise RuntimeError(f"OpenRouter недоступен после {max_retries} попыток: {last_err}")


def _extract_json(raw: str) -> dict:
    """Достаёт JSON из ответа (на случай обёрток ```json ... ``` или текста вокруг)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    return json.loads(raw)


_EXTRACT_JSON_HINT = (
    "\n\nВерни ТОЛЬКО валидный JSON строго по схеме (без markdown, без комментариев):\n"
    + json.dumps(EXTRACT_SCHEMA, ensure_ascii=False)
)


def _openai_extract(chunk: str) -> ExtractionResult:
    raw = _openai_chat(EXTRACT_SYSTEM + _EXTRACT_JSON_HINT, chunk, json_mode=True)
    try:
        return ExtractionResult(**_extract_json(raw))
    except Exception:
        return ExtractionResult()


def _openai_answer(question: str, context: str) -> str:
    return _openai_chat(ANSWER_SYSTEM,
                        f"ВОПРОС:\n{question}\n\nКОНТЕКСТ:\n{context}", max_tokens=1500)


# ===================== Anthropic (опционально) =====================

def _anthropic_extract(chunk: str) -> ExtractionResult:
    from anthropic import Anthropic
    client = Anthropic(api_key=settings.anthropic_api_key)
    tool = {"name": "record_extraction", "description": "Записать извлечённое.",
            "input_schema": EXTRACT_SCHEMA}
    resp = client.messages.create(
        model=settings.llm_model, max_tokens=2000, system=EXTRACT_SYSTEM,
        tools=[tool], tool_choice={"type": "tool", "name": "record_extraction"},
        messages=[{"role": "user", "content": chunk}])
    for block in resp.content:
        if block.type == "tool_use":
            return ExtractionResult(**block.input)
    return ExtractionResult()


def _anthropic_answer(question: str, context: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=settings.llm_model, max_tokens=1500, system=ANSWER_SYSTEM,
        messages=[{"role": "user", "content": f"ВОПРОС:\n{question}\n\nКОНТЕКСТ:\n{context}"}])
    return "".join(b.text for b in resp.content if b.type == "text")


# ===================== Публичный интерфейс =====================

def extract(chunk: str) -> ExtractionResult:
    if settings.llm_provider == "openai":
        return _openai_extract(chunk)
    if settings.llm_provider == "anthropic":
        return _anthropic_extract(chunk)
    return _ollama_extract(chunk)


def answer(question: str, context: str) -> str:
    if settings.llm_provider == "openai":
        return _openai_answer(question, context)
    if settings.llm_provider == "anthropic":
        return _anthropic_answer(question, context)
    return _ollama_answer(question, context)


def health() -> dict:
    if settings.llm_provider == "openai":
        return {"provider": "openai", "base_url": settings.openai_base_url,
                "model": settings.llm_model, "ok": bool(settings.openai_api_key),
                "key_set": bool(settings.openai_api_key)}
    if settings.llm_provider == "anthropic":
        return {"provider": "anthropic", "model": settings.llm_model,
                "ok": bool(settings.anthropic_api_key)}
    try:
        r = httpx.get(f"{settings.ollama_host}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        return {"provider": "ollama", "host": settings.ollama_host,
                "model": settings.llm_model, "ok": True,
                "model_pulled": any(settings.llm_model.split(":")[0] in m for m in models),
                "available": models}
    except Exception as e:
        return {"provider": "ollama", "host": settings.ollama_host, "ok": False,
                "error": str(e)}
