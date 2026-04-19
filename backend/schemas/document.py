from datetime import datetime
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
