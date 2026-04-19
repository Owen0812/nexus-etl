import hashlib

from backend.agents.state import DocumentState


def _sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def increment_checker_node(state: DocumentState) -> dict:
    """Compute SHA-256 of the file; skip pipeline if already processed."""
    file_hash = _sha256(state["file_path"])

    # TODO: query DB — e.g. `await db.scalar(select(Document).where(Document.file_hash == file_hash))`
    is_duplicate = False

    return {
        "file_hash": file_hash,
        "is_duplicate": is_duplicate,
        "stages_completed": ["increment_checker"],
    }
