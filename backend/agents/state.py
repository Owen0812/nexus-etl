import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class DocumentState(TypedDict):
    """Shared state flowing through the full ETL pipeline graph."""

    # ── Input ─────────────────────────────────────────────────────────────────
    document_id: str
    file_path: str
    filename: str

    # ── Increment Checker ─────────────────────────────────────────────────────
    file_hash: str
    is_duplicate: bool

    # ── Vision Extractor ──────────────────────────────────────────────────────
    raw_pages: list[dict]       # [{page_num, text, width, height}]
    extracted_tables: list[dict]  # [{page_num, table_index, data, vision_description}]
    extracted_images: list[dict]  # [{page_num, image_b64}]

    # ── Semantic Chunker ──────────────────────────────────────────────────────
    raw_chunks: list[dict]      # [{content, chunk_index, chunk_type, token_count}]

    # ── Metadata Tagger ───────────────────────────────────────────────────────
    doc_metadata: dict[str, Any]   # {title, author, date, language, domain, ...}
    chunk_metadata: list[dict]     # per-chunk tags

    # ── Quality Agent ─────────────────────────────────────────────────────────
    filtered_chunks: list[dict]    # chunks that passed quality threshold
    quality_report: dict[str, Any]

    # ── Control ───────────────────────────────────────────────────────────────
    processing_strategy: str   # "vision" | "text"
    current_stage: str
    stages_completed: Annotated[list[str], operator.add]
    error: str | None
    retry_count: Annotated[int, operator.add]

    # ── LLM messages (append-only) ────────────────────────────────────────────
    messages: Annotated[list, add_messages]
