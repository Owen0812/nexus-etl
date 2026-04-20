import uuid
from itertools import islice

from backend.agents.state import DocumentState
from backend.db.session import async_session_factory
from backend.models.chunk import Chunk
from backend.utils.embeddings import embed_texts

_EMBED_BATCH = 20


def _batched(seq, n):
    it = iter(seq)
    while batch := list(islice(it, n)):
        yield batch


async def embedding_writer_node(state: DocumentState) -> dict:
    """Embed all filtered chunks and persist to chunks table."""
    filtered_chunks = state.get("filtered_chunks", [])
    chunk_metadata_list = state.get("chunk_metadata", [])
    document_id = uuid.UUID(state["document_id"])

    if not filtered_chunks:
        return {"stages_completed": ["embedding_writer"]}

    # chunk_metadata[i] corresponds to raw_chunks[i] (same index as chunk_index)
    meta_by_idx: dict[int, dict] = {i: m for i, m in enumerate(chunk_metadata_list)}

    contents = [c["content"] for c in filtered_chunks]
    embeddings: list[list[float]] = []
    for batch in _batched(contents, _EMBED_BATCH):
        embeddings.extend(embed_texts(batch))

    async with async_session_factory() as session:
        for chunk, emb in zip(filtered_chunks, embeddings):
            idx = chunk.get("chunk_index", 0)
            session.add(Chunk(
                id=uuid.uuid4(),
                document_id=document_id,
                content=chunk["content"],
                chunk_index=idx,
                chunk_type=chunk.get("chunk_type"),
                token_count=chunk.get("token_count"),
                quality_score=chunk.get("quality_score"),
                embedding=emb,
                chunk_metadata=meta_by_idx.get(idx, {}),
            ))
        await session.commit()

    return {"stages_completed": ["embedding_writer"]}
