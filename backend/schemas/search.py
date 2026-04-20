from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    document_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    use_hyde: bool = True


class ChunkResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    chunk_type: str | None
    quality_score: float | None
    vector_score: float
    bm25_score: float
    rerank_score: float | None
    final_score: float


class SearchResponse(BaseModel):
    query: str
    hyde_query: str | None
    results: list[ChunkResult]
    latency_ms: int
