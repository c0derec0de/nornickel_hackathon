"""Юнит-тесты чистой логики SciGraph (без neo4j/chroma/fastembed/LLM).

Запуск из каталога backend:
    PYTHONPATH=. python tests/test_logic.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import ontology, schemas, llm            # noqa: E402
from app.ingest import loader                      # noqa: E402
from app.config import settings                    # noqa: E402

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {extra}")


def run():
    print("== ontology.canonical ==")
    check("electrowinning→электроэкстракция", ontology.canonical("electrowinning") == "электроэкстракция")
    check("ПВП→печь взвешенной плавки", ontology.canonical("ПВП") == "печь взвешенной плавки")
    check("регистр не важен", ontology.canonical("Catholyte") == "католит")
    check("неизвестное — как есть (trim)", ontology.canonical("  Никель ") == "Никель")

    print("== loader.chunk_text ==")
    t = "abcdefghij" * 20
    ch = loader.chunk_text(t, size=80, overlap=20)
    check("чанки нарезаны", len(ch) >= 2)
    check("overlap (шаг=size-overlap)", ch[1].startswith(t[60:70]))
    check("пустой текст → []", loader.chunk_text("   ", 80, 20) == [])
    check("max_chunks ограничивает", len(loader.chunk_text(t, 20, 5, max_chunks=3)) == 3)

    print("== loader на сид-корпусе (.md) ==")
    seed_dir = os.path.join(os.path.dirname(__file__), "..", "data", "seed")
    seed = loader.load_corpus(seed_dir)
    check("сид загружен", len(seed) >= 4, f"chunks={len(seed)}")
    check("есть doc/chunk_id/text", all(k in seed[0] for k in ("doc", "chunk_id", "text")))

    print("== schemas.ExtractionResult ==")
    sample = {
        "entities": [{"name": "обратный осмос", "type": "Process"},
                     {"name": "сульфаты", "type": "Material", "aliases": ["SO4"]}],
        "relations": [{"source": "обратный осмос", "target": "сухой остаток",
                       "type": "PRODUCES_OUTPUT",
                       "condition": {"quantity": "сухой остаток", "op": "<=",
                                     "value": 1000, "unit": "мг/дм3"}}],
        "constraints": [{"quantity": "сульфаты", "op": "range", "value": 200,
                         "value_max": 300, "unit": "мг/л"}],
        "geography": "РФ", "summary": "тест",
    }
    er = schemas.ExtractionResult(**sample)
    check("сущности распарсены", len(er.entities) == 2)
    check("связь с condition", er.relations[0].condition.value == 1000)
    check("range-ограничение", er.constraints[0].value_max == 300)

    print("== llm._extract_json ==")
    check("чистый JSON", llm._extract_json('{"a":1}') == {"a": 1})
    check("```json fenced```", llm._extract_json('```json\n{"a":2}\n```') == {"a": 2})
    check("текст вокруг JSON", llm._extract_json('Вот: {"a":3} готово') == {"a": 3})
    check("Qwen3 <think> отбрасывается",
          llm._extract_json('<think>подумаю…</think>{"a":4}') == {"a": 4})

    print("== схема/дефолты ==")
    check("типы сущностей в enum",
          "Material" in llm.EXTRACT_SCHEMA["properties"]["entities"]["items"]["properties"]["type"]["enum"])
    check("провайдер по умолчанию ollama", settings.llm_provider == "ollama")
    check("модель qwen по умолчанию", settings.llm_model.startswith("qwen"))

    # опционально: реальный корпус (если скачан)
    corpus = os.path.join(os.path.dirname(__file__), "..", "data", "corpus")
    real = list(loader.iter_files(corpus, name_filter=["Методы очистки шахтных"]))
    if real:
        print("== реальный .docx (корпус найден) ==")
        txt = loader._read_file(real[0])
        check("docx распарсен непусто", len(txt) > 200)
        check("кириллица на месте", any("а" <= c <= "я" for c in txt.lower()))
    else:
        print("== реальный корпус не скачан — docx-тест пропущен ==")

    print(f"\n==== ИТОГ: {PASS} passed, {FAIL} failed ====")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
