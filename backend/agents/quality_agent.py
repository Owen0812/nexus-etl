from backend.agents.state import DocumentState

_MIN_TOKENS = 20
_MAX_TOKENS = 1500
_PASS_THRESHOLD = 0.4


def _is_garbage(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return True
    printable_ratio = sum(1 for c in text if c.isprintable()) / max(len(text), 1)
    return printable_ratio < 0.5


def _score(chunk: dict, meta: dict) -> float:
    score = 1.0
    tokens = chunk.get("token_count", 0)

    if tokens < _MIN_TOKENS:
        score -= 0.4
    elif tokens > _MAX_TOKENS:
        score -= 0.2

    if _is_garbage(chunk.get("content", "")):
        score -= 0.6

    importance = float(meta.get("importance_score", 0.5))
    score = score * 0.7 + importance * 0.3

    return round(max(0.0, min(1.0, score)), 3)


def quality_agent_node(state: DocumentState) -> dict:
    """Score each chunk and filter below threshold; produce quality report."""
    raw_chunks = state.get("raw_chunks", [])
    chunk_metadata = state.get("chunk_metadata", [{}] * len(raw_chunks))

    filtered, scores = [], []
    for chunk, meta in zip(raw_chunks, chunk_metadata):
        s = _score(chunk, meta)
        if s >= _PASS_THRESHOLD:
            filtered.append({**chunk, "quality_score": s})
            scores.append(s)

    quality_report = {
        "total_chunks": len(raw_chunks),
        "passed_chunks": len(filtered),
        "filtered_out": len(raw_chunks) - len(filtered),
        "avg_quality_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "pass_rate": round(len(filtered) / max(len(raw_chunks), 1), 3),
    }

    return {
        "filtered_chunks": filtered,
        "quality_report": quality_report,
        "stages_completed": ["quality_agent"],
    }
