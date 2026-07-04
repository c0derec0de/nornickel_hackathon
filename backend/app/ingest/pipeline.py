"""Оркестрация импорта: loader -> LLM extract -> Neo4j + Chroma.

Ингест возобновляемый (пропускает уже загруженные чанки) и умеет работать фоново
с отслеживанием прогресса — под массовый корпус (1453 файла) и бесплатную локальную модель.
"""
import threading
import time
from ..config import settings
from ..db.neo4j_client import neo4j_client
from ..db.vector_store import vector_store
from .. import llm
from .loader import load_corpus


def _type_of(entities_map, name, default="Material"):
    return entities_map.get(name, default)


# ---- глобальный статус фонового ингеста ----
STATUS = {
    "running": False,
    "started_at": None,
    "docs_total": 0,
    "chunks_total": 0,
    "chunks_done": 0,
    "chunks_skipped": 0,
    "entities": 0,
    "relations": 0,
    "errors": 0,
    "current_doc": None,
    "finished_at": None,
}
_lock = threading.Lock()


def _reset_status():
    with _lock:
        STATUS.update({
            "running": True, "started_at": time.time(), "finished_at": None,
            "docs_total": 0, "chunks_total": 0, "chunks_done": 0,
            "chunks_skipped": 0, "entities": 0, "relations": 0, "errors": 0,
            "current_doc": None,
        })


def _run(reset, corpus_dir, max_files, name_filter, max_chunks_per_doc):
    _reset_status()
    if reset:
        neo4j_client.wipe()
        vector_store.wipe()
    neo4j_client.init_schema()

    cap = max_chunks_per_doc if max_chunks_per_doc is not None else settings.max_chunks_per_doc
    items = load_corpus(corpus_dir, max_files=max_files, name_filter=name_filter,
                        max_chunks_per_doc=cap)
    # если корпус ещё не скачан — берём демо-сид, чтобы приложение работало из коробки
    if not items and corpus_dir is None:
        print("[ingest] корпус пуст — использую демо-сид data/seed")
        items = load_corpus("data/seed", max_chunks_per_doc=cap)

    with _lock:
        STATUS["chunks_total"] = len(items)
        STATUS["docs_total"] = len({it["doc"] for it in items})

    # возобновляемость: пропускаем уже загруженные чанки
    done_ids = vector_store.existing_ids([it["chunk_id"] for it in items]) if not reset else set()

    for item in items:
        with _lock:
            STATUS["current_doc"] = item["doc"]
        if item["chunk_id"] in done_ids:
            with _lock:
                STATUS["chunks_skipped"] += 1
                STATUS["chunks_done"] += 1
            continue

        try:
            result = llm.extract(item["text"])
        except Exception as e:
            with _lock:
                STATUS["errors"] += 1
            print(f"[extract error] {item['chunk_id']}: {e}")
            result = None

        meta = {"doc": item["doc"], "chunk_id": item["chunk_id"]}
        if result and result.geography:
            meta["geo"] = result.geography
        try:
            vector_store.add([item["chunk_id"]], [item["text"]], [meta])
        except Exception as e:
            print(f"[vector error] {item['chunk_id']}: {e}")

        if result:
            etype = {}
            for ent in result.entities:
                try:
                    neo4j_client.upsert_entity(ent.name, ent.type, aliases=ent.aliases,
                                               source=item["doc"], geo=result.geography)
                    etype[ent.name] = ent.type
                    with _lock:
                        STATUS["entities"] += 1
                except Exception:
                    pass
            for rel in result.relations:
                cond = rel.condition.model_dump() if rel.condition else None
                try:
                    neo4j_client.upsert_relation(
                        rel.source, _type_of(etype, rel.source),
                        rel.target, _type_of(etype, rel.target, "Property"),
                        rel.type, source=item["doc"], condition=cond)
                    with _lock:
                        STATUS["relations"] += 1
                except Exception:
                    pass

        with _lock:
            STATUS["chunks_done"] += 1

    with _lock:
        STATUS["running"] = False
        STATUS["current_doc"] = None
        STATUS["finished_at"] = time.time()


def ingest(reset: bool = False, corpus_dir: str | None = None,
           max_files: int | None = None, name_filter: list[str] | None = None,
           max_chunks_per_doc: int | None = None):
    """Синхронный ингест (для малых объёмов / скриптов)."""
    _run(reset, corpus_dir, max_files, name_filter, max_chunks_per_doc)
    with _lock:
        return dict(STATUS)


def start_background(reset: bool = False, corpus_dir: str | None = None,
                     max_files: int | None = None, name_filter: list[str] | None = None,
                     max_chunks_per_doc: int | None = None) -> bool:
    """Запускает ингест в фоне. Возвращает False если уже идёт."""
    with _lock:
        if STATUS["running"]:
            return False
    t = threading.Thread(
        target=_run,
        args=(reset, corpus_dir, max_files, name_filter, max_chunks_per_doc),
        daemon=True)
    t.start()
    return True


def status() -> dict:
    with _lock:
        s = dict(STATUS)
    total, done = s["chunks_total"], s["chunks_done"]
    s["progress"] = round(done / total, 3) if total else 0.0
    if s["running"] and s["started_at"] and done > s["chunks_skipped"]:
        processed = done - s["chunks_skipped"]
        rate = processed / max(time.time() - s["started_at"], 1)
        remaining = total - done
        s["eta_minutes"] = round(remaining / rate / 60, 1) if rate > 0 else None
    return s
