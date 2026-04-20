import uuid
from datetime import datetime, timezone
from typing import Callable

from backend.celery_app import celery_app
from backend.agents.graph import pipeline_graph
from backend.db.session import async_session_factory
from backend.models.document import Document, DocumentStatus
from backend.models.pipeline_run import PipelineRun, RunStatus
from backend.utils.langfuse_client import get_langfuse_handler


async def _run_pipeline(
    document_id: str,
    file_path: str,
    filename: str,
    celery_task_id: str,
    update_fn: Callable[[dict], None] | None = None,
) -> dict:
    """Full async pipeline: streaming graph + DB status writeback."""
    doc_uuid = uuid.UUID(document_id)
    started_at = datetime.now(timezone.utc)
    run_id = uuid.uuid4()

    # Mark document as PROCESSING and create PipelineRun record
    async with async_session_factory() as session:
        doc = await session.get(Document, doc_uuid)
        if doc:
            doc.status = DocumentStatus.PROCESSING
        session.add(PipelineRun(
            id=run_id,
            document_id=doc_uuid,
            celery_task_id=celery_task_id,
            status=RunStatus.RUNNING,
            started_at=started_at,
        ))
        await session.commit()

    langfuse_handler = get_langfuse_handler()
    initial_state = {
        "document_id": document_id,
        "file_path": file_path,
        "filename": filename,
        "stages_completed": [],
        "retry_count": 0,
        "error": None,
        "messages": [],
    }
    config = {
        "configurable": {"thread_id": document_id},
        "callbacks": [langfuse_handler] if langfuse_handler else [],
    }

    try:
        # Stream node-by-node; each snapshot is the full accumulated state
        final_state: dict = {}
        async for state_snapshot in pipeline_graph.astream(
            initial_state, config=config, stream_mode="values"
        ):
            final_state = state_snapshot
            if update_fn:
                stages = state_snapshot.get("stages_completed") or []
                if stages:
                    update_fn({"stages_completed": stages})

        finished_at = datetime.now(timezone.utc)
        chunk_count = len(final_state.get("filtered_chunks", []))

        async with async_session_factory() as session:
            doc = await session.get(Document, doc_uuid)
            if doc:
                doc.status = DocumentStatus.COMPLETED
                doc.file_hash = final_state.get("file_hash")

            run = await session.get(PipelineRun, run_id)
            if run:
                run.status = RunStatus.SUCCESS
                run.stages_completed = final_state.get("stages_completed", [])
                run.chunk_count = chunk_count
                run.finished_at = finished_at
                run.duration_seconds = (finished_at - started_at).total_seconds()

            await session.commit()

        return {
            "status": "success",
            "document_id": document_id,
            "chunk_count": chunk_count,
            "stages_completed": final_state.get("stages_completed", []),
            "quality_report": final_state.get("quality_report", {}),
        }

    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        error_msg = str(exc)

        async with async_session_factory() as session:
            doc = await session.get(Document, doc_uuid)
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_message = error_msg[:1000]

            run = await session.get(PipelineRun, run_id)
            if run:
                run.status = RunStatus.FAILED
                run.error_detail = error_msg[:2000]
                run.finished_at = finished_at
                run.duration_seconds = (finished_at - started_at).total_seconds()

            await session.commit()

        raise


@celery_app.task(
    bind=True,
    name="backend.tasks.pipeline.run_etl_pipeline",
    max_retries=3,
    default_retry_delay=60,
)
def run_etl_pipeline(self, document_id: str, file_path: str, filename: str):
    """Celery entry-point: streams LangGraph pipeline and pushes per-stage progress."""
    def _push_progress(meta: dict):
        self.update_state(state="PROGRESS", meta=meta)

    from backend.celery_app import get_worker_loop
    loop = get_worker_loop()
    try:
        return loop.run_until_complete(
            _run_pipeline(document_id, file_path, filename, self.request.id or "", _push_progress)
        )
    except Exception as exc:
        raise self.retry(exc=exc)
