import json
import re
import time
from collections import Counter
from pathlib import Path

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

_MAX_ATTEMPTS = 3

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "this", "that", "these",
    "those", "with", "from", "into", "for", "and", "but", "or",
}


def _fast_llm() -> ChatOpenAI:
    """Lightweight model — sufficient for structured JSON extraction."""
    return ChatOpenAI(
        model=settings.qwen_fast_model,
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_api_base,
        temperature=0,
    )


def _invoke_with_retry(llm: ChatOpenAI, messages: list, fallback: dict) -> dict:
    """Call LLM and parse JSON; retry up to 3x with exponential backoff.
    Returns deterministic rule-based fallback if all attempts fail.
    """
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = llm.invoke(messages)
            return json.loads(resp.content)
        except Exception:
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(2 ** attempt)  # 1s → 2s
    return fallback


# ── Rule-based fallbacks ──────────────────────────────────────────────────────

def _rule_doc_metadata(text: str, filename: str) -> dict:
    """Deterministic fallback: extract metadata without LLM."""
    title = Path(filename).stem.replace("_", " ").replace("-", " ").title()

    # Detect language by CJK character ratio
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    language = "zh" if cjk_count > max(len(text), 1) * 0.1 else "en"

    # Top keywords from word frequency
    words = [w.lower() for w in re.findall(r"\b[a-zA-Z\u4e00-\u9fff]{3,}\b", text[:4000])]
    freq = Counter(w for w in words if w not in _STOP_WORDS)
    keywords = [w for w, _ in freq.most_common(10)]

    return {
        "title": title,
        "author": None,
        "date": None,
        "language": language,
        "domain": "general",
        "summary": text[:200].strip(),
        "keywords": keywords,
    }


def _rule_chunk_metadata(text: str) -> dict:
    """Deterministic fallback: classify chunk type and extract entities without LLM."""
    if re.search(r"\t.*\t|\|.*\|", text):
        content_type = "table"
    elif re.search(r"^\s*[-•*]\s", text, re.MULTILINE):
        content_type = "list"
    elif len(text.strip()) < 100 and not text.strip().endswith("."):
        content_type = "header"
    else:
        content_type = "prose"

    entities = list(dict.fromkeys(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)))[:5]

    return {
        "section_title": None,
        "content_type": content_type,
        "entities": entities,
        "importance_score": 0.5,
    }


# ── LLM tagging ───────────────────────────────────────────────────────────────

def _tag_document(text: str, llm: ChatOpenAI, filename: str) -> dict:
    return _invoke_with_retry(
        llm,
        messages=[
            SystemMessage(content=f"Return ONLY valid JSON matching: {json.dumps(_DOC_SCHEMA)}"),
            HumanMessage(content=text[:3000]),
        ],
        fallback=_rule_doc_metadata(text, filename),
    )


def _tag_chunk(text: str, llm: ChatOpenAI) -> dict:
    return _invoke_with_retry(
        llm,
        messages=[
            SystemMessage(content=f"Return ONLY valid JSON matching: {json.dumps(_CHUNK_SCHEMA)}"),
            HumanMessage(content=text[:1000]),
        ],
        fallback=_rule_chunk_metadata(text),
    )


def metadata_tagger_node(state: DocumentState) -> dict:
    """Extract document-level and per-chunk metadata.

    Uses lightweight qwen_fast_model — sufficient for structured JSON tasks.
    Falls back to deterministic rule-based extraction on repeated LLM failure.
    """
    llm = _fast_llm()

    first_pages_text = " ".join(p.get("text", "") for p in state.get("raw_pages", [])[:3])
    doc_metadata = _tag_document(first_pages_text, llm, state.get("filename", ""))

    chunk_metadata = [
        _tag_chunk(c.get("content", ""), llm)
        for c in state.get("raw_chunks", [])
    ]

    return {
        "doc_metadata": doc_metadata,
        "chunk_metadata": chunk_metadata,
        "stages_completed": ["metadata_tagger"],
    }
