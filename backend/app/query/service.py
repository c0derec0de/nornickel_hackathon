from .retriever import hybrid_retrieve
from ..db.neo4j_client import neo4j_client
from .. import llm
from ..schemas import QueryRequest, QueryResponse


def answer_query(req: QueryRequest) -> QueryResponse:
    context, citations, graph = hybrid_retrieve(req)

    if context.strip():
        text = llm.answer(req.question, context)
    else:
        text = ("В базе пока нет данных по этому запросу. Загрузите корпус документов "
                "(backend/data/corpus) и выполните переиндексацию.")

    gaps = neo4j_client.find_gaps()
    contradictions = neo4j_client.find_contradictions()

    return QueryResponse(
        answer=text,
        citations=citations,
        graph=graph,
        gaps=gaps,
        contradictions=contradictions,
    )
