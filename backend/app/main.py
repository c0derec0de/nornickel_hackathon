from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import QueryRequest, QueryResponse
from .query.service import answer_query
from .ingest import pipeline
from .db.neo4j_client import neo4j_client
from .db.vector_store import vector_store
from . import llm

app = FastAPI(title="SciGraph API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "llm": llm.health()}


@app.get("/stats")
def stats():
    try:
        g = neo4j_client.stats()
    except Exception as e:
        g = {"error": str(e)}
    try:
        vc = vector_store.count()
    except Exception:
        vc = None
    return {"graph": g, "vectors": vc}


@app.post("/ingest")
def run_ingest(reset: bool = False, background: bool = True,
               max_files: int | None = None, name_filter: str | None = None,
               max_chunks_per_doc: int | None = None):
    """Импорт корпуса → граф + вектора. Возобновляемый.

    - background=True: запускает в фоне, следи через GET /ingest/status
    - max_files / name_filter (CSV подстрок) / max_chunks_per_doc — контроль объёма
    """
    filters = [s.strip() for s in name_filter.split(",")] if name_filter else None
    if background:
        ok = pipeline.start_background(reset=reset, max_files=max_files,
                                       name_filter=filters, max_chunks_per_doc=max_chunks_per_doc)
        if not ok:
            raise HTTPException(409, "Ингест уже выполняется")
        return {"started": True, "status_url": "/ingest/status"}
    try:
        return pipeline.ingest(reset=reset, max_files=max_files,
                               name_filter=filters, max_chunks_per_doc=max_chunks_per_doc)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/ingest/status")
def ingest_status():
    return pipeline.status()


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    try:
        return answer_query(req)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/graph")
def graph(entity: str, depth: int = 2):
    nodes, edges = neo4j_client.subgraph_for([entity], depth=depth)
    return {"nodes": nodes, "edges": edges}
