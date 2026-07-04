from typing import Optional
from pydantic import BaseModel, Field


class NumericConstraint(BaseModel):
    quantity: str = Field(description="что измеряется, напр. 'сульфаты', 'температура'")
    op: str = Field(description="<=, >=, =, range")
    value: float
    value_max: Optional[float] = Field(default=None, description="для range — верхняя граница")
    unit: str = Field(default="", description="мг/л, °C, т/сут, м3/ч")


class ExtractedEntity(BaseModel):
    name: str
    type: str = Field(description="один из типов онтологии: Material, Process, ...")
    aliases: list[str] = Field(default_factory=list)


class ExtractedRelation(BaseModel):
    source: str = Field(description="имя исходной сущности")
    target: str = Field(description="имя целевой сущности")
    type: str = Field(description="тип связи из онтологии")
    condition: Optional[NumericConstraint] = None


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
    constraints: list[NumericConstraint] = Field(default_factory=list)
    geography: Optional[str] = Field(default=None, description="РФ / зарубеж / регион")
    summary: str = Field(default="", description="1-2 предложения о содержании чанка")


# ---------- API ----------

class QueryRequest(BaseModel):
    question: str
    geo: Optional[str] = None          # фильтр: РФ / зарубеж
    year_from: Optional[int] = None
    material: Optional[str] = None


class Citation(BaseModel):
    source: str
    snippet: str
    confidence: float = 0.7


class GraphNode(BaseModel):
    id: str
    label: str
    type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    graph: GraphData = Field(default_factory=GraphData)
    gaps: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
