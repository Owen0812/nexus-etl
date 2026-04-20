"""BGE-Reranker wrapper with graceful fallback.

Install to enable:
    pip install FlagEmbedding  # pulls torch automatically

Without FlagEmbedding installed the reranker silently falls back to
returning the input list unchanged (ordered by RRF score).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class Reranker:
    """Lazy-loaded BGE cross-encoder reranker (BAAI/bge-reranker-base).

    Thread-safe: model is loaded once on first call.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        self._model_name = model_name
        self._model = None
        self._attempted = False

    def _load(self) -> None:
        if self._attempted:
            return
        self._attempted = True
        try:
            from FlagEmbedding import FlagReranker
            self._model = FlagReranker(self._model_name, use_fp16=True)
            logger.info("BGE-Reranker loaded: %s", self._model_name)
        except ImportError:
            logger.warning(
                "FlagEmbedding not installed — reranker disabled. "
                "Run `pip install FlagEmbedding` to enable."
            )
        except Exception as e:
            logger.warning("Failed to load BGE-Reranker: %s", e)

    def rerank(self, query: str, chunks: list[dict], top_k: int) -> list[dict]:
        """Score and sort chunks by cross-encoder relevance; slice to top_k.

        Each chunk dict gets a `rerank_score` key added in-place.
        Falls back to identity order if model unavailable.
        """
        self._load()

        if not chunks:
            return chunks

        if self._model is None:
            for c in chunks:
                c.setdefault("rerank_score", None)
            return chunks[:top_k]

        pairs = [[query, c.get("content", "")] for c in chunks]
        raw_scores = self._model.compute_score(pairs, normalize=True)

        if isinstance(raw_scores, float):
            raw_scores = [raw_scores]

        ranked = sorted(
            zip(chunks, raw_scores),
            key=lambda x: x[1],
            reverse=True,
        )
        for chunk, score in ranked:
            chunk["rerank_score"] = round(float(score), 4)

        return [c for c, _ in ranked[:top_k]]


# Module-level singleton
reranker = Reranker()
