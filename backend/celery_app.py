import asyncio
from celery import Celery
from celery.signals import worker_process_init
from backend.config import settings

celery_app = Celery(
    "nexus_etl",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.tasks.pipeline"],
)

@worker_process_init.connect
def reset_db_pool(**kwargs):
    """Dispose inherited asyncpg connections after fork — each worker needs its own pool."""
    from backend.db.session import engine
    asyncio.run(engine.dispose())


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "backend.tasks.pipeline.*": {"queue": "pipeline"},
    },
)
