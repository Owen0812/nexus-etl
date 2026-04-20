"""Baseline 1: Fixed-size LangChain character splitter (no semantic awareness)."""
from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 0) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


def process_file(file_path: str) -> list[dict]:
    """Extract plain text from a file and apply fixed-size chunking."""
    import pdfplumber
    from pathlib import Path

    suffix = Path(file_path).suffix.lower()
    text = ""

    if suffix == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    elif suffix == ".docx":
        from docx import Document as DocxDocument
        doc = DocxDocument(file_path)
        text = "\n".join(p.text for p in doc.paragraphs)
    elif suffix in (".html", ".htm"):
        from bs4 import BeautifulSoup
        from pathlib import Path as P
        soup = BeautifulSoup(P(file_path).read_text(encoding="utf-8", errors="replace"), "lxml")
        text = soup.get_text(separator="\n", strip=True)

    chunks = chunk_text(text)
    return [
        {"content": c, "chunk_index": i, "chunk_type": "text", "method": "fixed_size"}
        for i, c in enumerate(chunks)
    ]
