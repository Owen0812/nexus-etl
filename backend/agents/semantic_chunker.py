import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.agents.state import DocumentState

_ENCODER = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_ENCODER.encode(text))


def semantic_chunker_node(state: DocumentState) -> dict:
    """Split pages into semantically coherent chunks; append table chunks separately."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        length_function=_token_len,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )

    full_text = "\n\n".join(
        f"[Page {p['page_num']}]\n{p['text']}"
        for p in state.get("raw_pages", [])
        if p.get("text", "").strip()
    )

    splits = splitter.split_text(full_text)
    chunks = [
        {
            "content": s,
            "chunk_index": i,
            "chunk_type": "text",
            "token_count": _token_len(s),
        }
        for i, s in enumerate(splits)
    ]

    # Append table chunks
    for tbl in state.get("extracted_tables", []):
        rows = tbl.get("data") or []
        table_text = "\n".join(
            "\t".join(str(cell or "") for cell in row) for row in rows if row
        )
        if table_text.strip():
            chunks.append({
                "content": table_text,
                "chunk_index": len(chunks),
                "chunk_type": "table",
                "token_count": _token_len(table_text),
                "source_page": tbl.get("page_num"),
            })

    return {
        "raw_chunks": chunks,
        "stages_completed": ["semantic_chunker"],
    }
