from langfuse.callback import CallbackHandler
from backend.config import settings


def get_langfuse_handler() -> CallbackHandler | None:
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    return CallbackHandler(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
