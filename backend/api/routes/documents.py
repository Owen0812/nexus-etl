import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.config import settings
from backend.models.document import Document, DocumentStatus
from backend.tasks.pipeline import run_etl_pipeline

router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid.uuid4())
    file_path = upload_dir / f"{doc_id}_{file.filename}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    document = Document(
        id=uuid.UUID(doc_id),
        filename=file.filename,
        file_path=str(file_path),
        file_size=file_path.stat().st_size,
        mime_type=file.content_type,
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    await db.flush()

    task = run_etl_pipeline.delay(doc_id, str(file_path), file.filename)

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "task_id": task.id,
        "status": "processing",
    }


@router.get("/{document_id}")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status,
        "file_hash": doc.file_hash,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/")
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).offset(skip).limit(limit).order_by(Document.created_at.desc())
    )
    return [
        {"id": str(d.id), "filename": d.filename, "status": d.status, "created_at": d.created_at.isoformat()}
        for d in result.scalars().all()
    ]
