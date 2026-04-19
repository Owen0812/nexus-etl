import asyncio

from backend.celery_app import celery_app
from backend.agents.graph import pipeline_graph
from backend.utils.langfuse_client import get_langfuse_handler


@celery_app.task(
    bind=True,
    name="backend.tasks.pipeline.run_etl_pipeline",
    max_retries=3,
    default_retry_delay=60,
)
def run_etl_pipeline(self, document_id: str, file_path: str, filename: str):
    """Celery entry-point: runs the full LangGraph pipeline for one document."""
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
        result = asyncio.run(pipeline_graph.ainvoke(initial_state, config=config))
        return {
            "status": "success",
            "document_id": document_id,
            "chunk_count": len(result.get("filtered_chunks", [])),
            "stages_completed": result.get("stages_completed", []),
            "quality_report": result.get("quality_report", {}),
        }
    except Exception as exc:
        raise self.retry(exc=exc)
