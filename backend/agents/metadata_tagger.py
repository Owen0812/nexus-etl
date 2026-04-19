import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.agents.state import DocumentState
from backend.config import settings

_DOC_SCHEMA = {
    "title": "string",
    "author": "string or null",
    "date": "ISO date or null",
    "language": "zh | en | other",
    "domain": "finance | medical | legal | tech | general",
    "summary": "string ≤200 chars",
    "keywords": ["string"],
}

_CHUNK_SCHEMA = {
    "section_title": "string or null",
    "content_type": "prose | table | list | header | formula",
    "entities": ["string"],
    "importance_score": "float 0-1",
}


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.qwen_model,
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_api_base,
        temperature=0,
    )


def _safe_json(text: str, fallback: dict) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def _tag_document(text: str, llm: ChatOpenAI) -> dict:
    resp = llm.invoke([
        SystemMessage(content=f"Return ONLY valid JSON matching: {json.dumps(_DOC_SCHEMA)}"),
        HumanMessage(content=text[:3000]),
    ])
    return _safe_json(resp.content, {"language": "unknown", "domain": "general", "keywords": []})


def _tag_chunk(text: str, llm: ChatOpenAI) -> dict:
    resp = llm.invoke([
        SystemMessage(content=f"Return ONLY valid JSON matching: {json.dumps(_CHUNK_SCHEMA)}"),
        HumanMessage(content=text[:1000]),
    ])
    return _safe_json(resp.content, {"content_type": "prose", "entities": [], "importance_score": 0.5})


def metadata_tagger_node(state: DocumentState) -> dict:
    """Extract document-level and per-chunk metadata with LLM."""
    llm = _llm()

    first_pages_text = " ".join(p.get("text", "") for p in state.get("raw_pages", [])[:3])
    doc_metadata = _tag_document(first_pages_text, llm)

    chunk_metadata = [
        _tag_chunk(c.get("content", ""), llm)
        for c in state.get("raw_chunks", [])
    ]

    return {
        "doc_metadata": doc_metadata,
        "chunk_metadata": chunk_metadata,
        "stages_completed": ["metadata_tagger"],
    }
