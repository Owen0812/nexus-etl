from datetime import datetime
from typing import Any
from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    task_id: str
    status: str


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    file_hash: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkResponse(BaseModel):
    id: str
    chunk_index: int
    chunk_type: str | None
    token_count: int | None
    quality_score: float | None
    content: str
    chunk_metadata: dict[str, Any] | None

    model_config = {"from_attributes": True}
