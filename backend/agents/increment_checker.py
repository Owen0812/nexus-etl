import hashlib
import uuid

from sqlalchemy import select

from backend.agents.state import DocumentState
from backend.db.session import async_session_factory
from backend.models.document import Document, DocumentStatus


def _sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


async def increment_checker_node(state: DocumentState) -> dict:
    """Compute SHA-256; skip pipeline if identical file already completed."""
    file_hash = _sha256(state["file_path"])

    async with async_session_factory() as session:
        existing = await session.scalar(
            select(Document).where(
                Document.file_hash == file_hash,
                Document.status == DocumentStatus.COMPLETED,
                # Exclude the current document being processed
                Document.id != uuid.UUID(state["document_id"]),
            )
        )

    return {
        "file_hash": file_hash,
        "is_duplicate": existing is not None,
        "stages_completed": ["increment_checker"],
    }
