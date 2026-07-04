"""Гибридный retrieval: семантика (Chroma) + расширение подграфа (Neo4j)."""
from ..db.vector_store import vector_store
from ..db.neo4j_client import neo4j_client
from ..schemas import QueryRequest, Citation, GraphData, GraphNode, GraphEdge


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

    # подграф: сущности из документов-источников найденных чанков + их окружение
    docs = list({c["meta"].get("doc") for c in chunks if c["meta"].get("doc")})
    seed_names = neo4j_client.entities_from_sources(docs)
    nodes, edges = neo4j_client.subgraph_for(seed_names, depth=2)
    graph = GraphData(
        nodes=[GraphNode(id=n["id"], label=n["label"], type=n["type"]) for n in nodes],
        edges=[GraphEdge(source=e["source"], target=e["target"], type=e["type"]) for e in edges],
    )

    context = "\n\n".join(
        f"[{c['meta'].get('doc','?')}] {c['text']}" for c in chunks)
    return context, citations, graph
