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

_worker_loop: asyncio.AbstractEventLoop | None = None


@worker_process_init.connect
def init_worker_event_loop(**kwargs):
    """Create a persistent event loop per worker process; dispose inherited asyncpg pool."""
    global _worker_loop
    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)
    from backend.db.session import engine
    _worker_loop.run_until_complete(engine.dispose())


def get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


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
