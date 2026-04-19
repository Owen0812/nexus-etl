from openai import OpenAI
from backend.config import settings


def _client() -> OpenAI:
    return OpenAI(api_key=settings.qwen_api_key, base_url=settings.qwen_api_base)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed via Qwen text-embedding model."""
    resp = _client().embeddings.create(model=settings.embedding_model, input=texts)
    return [item.embedding for item in resp.data]


def embed_single(text: str) -> list[float]:
    return embed_texts([text])[0]
