"""Hybrid retrieval endpoint: BM25 + pgvector + HyDE + BGE-Reranker.

Pipeline:
  1. HyDE  — fast LLM generates a hypothetical answer to bridge query/doc vector gap
  2. Embed — embed the hypothetical answer (or raw query if HyDE disabled)
  3. Dense — pgvector cosine similarity, top-N candidates
  4. Sparse — PostgreSQL full-text ts_rank_cd, top-N candidates
  5. RRF   — Reciprocal Rank Fusion merges both ranked lists
  6. Rerank — BGE cross-encoder rescores fused candidates, returns top_k
"""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.config import settings
from backend.schemas.search import ChunkResult, SearchRequest, SearchResponse
from backend.utils.embeddings import embed_single
from backend.utils.reranker import reranker

router = APIRouter()

_RRF_K = 60        # RRF constant — 60 is standard
_CANDIDATES = 20   # per-source candidates before fusion


# ── HyDE ─────────────────────────────────────────────────────────────────────

def _hyde_expand(query: str) -> str:
    """Generate a hypothetical document passage that would answer the query.

    Embeds the generated passage instead of the raw query — reduces the
    vector-space gap between short queries and long document chunks.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.qwen_fast_model,
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_api_base,
        temperature=0.3,
        max_tokens=256,
    )
    resp = llm.invoke([
        SystemMessage(content=(
            "You are a document retrieval assistant. "
            "Write a concise passage (2-4 sentences) that would directly answer the user's question. "
            "Write as if it is an excerpt from an authoritative document. Return the passage only."
        )),
        HumanMessage(content=query),
    ])
    return resp.content.strip()


# ── Database queries ──────────────────────────────────────────────────────────

async def _vector_search(
    db: AsyncSession,
    embedding: list[float],
    document_id: str | None,
    limit: int,
) -> list[dict]:
    vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
    where = "AND document_id = :doc_id" if document_id else ""
    sql = text(f"""
        SELECT
            id::text AS chunk_id,
            document_id::text,
            content,
            chunk_type,
            quality_score,
            chunk_metadata,
            1 - (embedding <=> :embedding::vector) AS vector_score
        FROM chunks
        WHERE embedding IS NOT NULL {where}
        ORDER BY embedding <=> :embedding::vector
        LIMIT :limit
    """)
    params: dict = {"embedding": vec_literal, "limit": limit}
    if document_id:
        params["doc_id"] = document_id
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]


async def _bm25_search(
    db: AsyncSession,
    query: str,
    document_id: str | None,
    limit: int,
) -> list[dict]:
    where = "AND document_id = :doc_id" if document_id else ""
    sql = text(f"""
        SELECT
            id::text AS chunk_id,
            document_id::text,
            content,
            chunk_type,
            quality_score,
            chunk_metadata,
            ts_rank_cd(
                to_tsvector('simple', content),
                plainto_tsquery('simple', :query)
            ) AS bm25_score
        FROM chunks
        WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', :query) {where}
        ORDER BY bm25_score DESC
        LIMIT :limit
    """)
    params: dict = {"query": query, "limit": limit}
    if document_id:
        params["doc_id"] = document_id
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]


# ── RRF fusion ────────────────────────────────────────────────────────────────

def _rrf_merge(
    vector_hits: list[dict],
    bm25_hits: list[dict],
) -> list[dict]:
    """Combine two ranked lists via Reciprocal Rank Fusion."""
    by_id: dict[str, dict] = {}
    rrf_scores: dict[str, float] = {}

    for rank, hit in enumerate(vector_hits, 1):
        cid = hit["chunk_id"]
        by_id[cid] = hit
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank)

    for rank, hit in enumerate(bm25_hits, 1):
        cid = hit["chunk_id"]
        by_id[cid] = {**by_id.get(cid, hit), "bm25_score": hit["bm25_score"]}
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank)

    ranked_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
    result = []
    for cid in ranked_ids:
        chunk = by_id[cid]
        chunk["final_score"] = round(rrf_scores[cid], 6)
        chunk.setdefault("vector_score", 0.0)
        chunk.setdefault("bm25_score", 0.0)
        result.append(chunk)
    return result


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Three-stage hybrid retrieval: BM25 + pgvector → RRF → BGE-Reranker."""
    t_start = time.perf_counter()
    hyde_query: str | None = None

    # ① HyDE expansion
    if request.use_hyde:
        try:
            hyde_query = _hyde_expand(request.query)
            embed_input = hyde_query
        except Exception:
            embed_input = request.query
    else:
        embed_input = request.query

    # ② Embed
    try:
        query_embedding = embed_single(embed_input)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding service error: {e}")

    # ③ Dense + Sparse retrieval
    vector_hits, bm25_hits = await _vector_search(
        db, query_embedding, request.document_id, _CANDIDATES
    ), await _bm25_search(
        db, request.query, request.document_id, _CANDIDATES
    )

    # ④ RRF fusion
    fused = _rrf_merge(vector_hits, bm25_hits)

    # ⑤ BGE-Reranker precision rerank
    reranked = reranker.rerank(request.query, fused, top_k=request.top_k)

    latency_ms = int((time.perf_counter() - t_start) * 1000)

    results = [
        ChunkResult(
            chunk_id=c["chunk_id"],
            document_id=c["document_id"],
            content=c["content"],
            chunk_type=c.get("chunk_type"),
            quality_score=c.get("quality_score"),
            vector_score=round(float(c.get("vector_score") or 0.0), 4),
            bm25_score=round(float(c.get("bm25_score") or 0.0), 4),
            rerank_score=c.get("rerank_score"),
            final_score=round(float(c.get("final_score") or 0.0), 6),
        )
        for c in reranked
    ]

    return SearchResponse(
        query=request.query,
        hyde_query=hyde_query,
        results=results,
        latency_ms=latency_ms,
    )
