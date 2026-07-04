"""Гибридный retrieval: семантика (Chroma) + расширение подграфа (Neo4j)."""
import re
from ..db.vector_store import vector_store
from ..db.neo4j_client import neo4j_client
from ..schemas import QueryRequest, Citation, GraphData, GraphNode, GraphEdge


def _extract_entity_names(chunks) -> list[str]:
    """Простое извлечение кандидатов-сущностей из найденных чанков по капитализации/терминам.
    Для подграфа достаточно передать имена — Neo4j сматчит существующие."""
    names = set()
    for c in chunks:
        for m in re.findall(r"[А-ЯЁA-Z][а-яёa-z]{3,}(?:\s[а-яёa-z]+){0,2}", c["text"]):
            names.add(m.strip())
    return list(names)[:25]


def hybrid_retrieve(req: QueryRequest, k: int = 6):
    where = None
    if req.geo:
        where = {"geo": req.geo}

    chunks = vector_store.query(req.question, k=k, where=where)
    if not chunks:  # fallback без фильтра
        chunks = vector_store.query(req.question, k=k)

    # цитаты
    citations = [
        Citation(source=c["meta"].get("doc", "?"),
                 snippet=c["text"][:280],
                 confidence=round(1 - (c["distance"] or 0), 2))
        for c in chunks
    ]

    # подграф вокруг сущностей
    seed_names = _extract_entity_names(chunks)
    nodes, edges = neo4j_client.subgraph_for(seed_names, depth=2)
    graph = GraphData(
        nodes=[GraphNode(id=n["id"], label=n["label"], type=n["type"]) for n in nodes],
        edges=[GraphEdge(source=e["source"], target=e["target"], type=e["type"]) for e in edges],
    )

    context = "\n\n".join(
        f"[{c['meta'].get('doc','?')}] {c['text']}" for c in chunks)
    return context, citations, graph
