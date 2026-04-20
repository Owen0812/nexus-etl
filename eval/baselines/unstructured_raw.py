"""Baseline 2: unstructured direct output — raw element list, no chunking."""
from __future__ import annotations

from pathlib import Path


def process_file(file_path: str) -> list[dict]:
    """Use unstructured to partition a document; return raw elements as chunks."""
    from unstructured.partition.auto import partition

    elements = partition(filename=file_path)
    chunks = []
    for i, el in enumerate(elements):
        text = str(el).strip()
        if not text:
            continue
        chunks.append({
            "content": text,
            "chunk_index": i,
            "chunk_type": type(el).__name__.lower(),
            "method": "unstructured_raw",
        })
    return chunks
