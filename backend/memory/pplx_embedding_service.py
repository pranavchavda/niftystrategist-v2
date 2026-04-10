"""Perplexity Embedding Service for cross-thread search.

Uses pplx-embed-context-v1-0.6b — contextualized embeddings optimized
for document chunks that share context (conversation turns).

1024 dimensions, 32K token context, $0.008/1M tokens.
API: OpenAI-compatible POST /embeddings via api.perplexity.ai.
"""

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Dict, List

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class PplxEmbeddingResult:
    embedding: List[float]
    cached: bool = False


class PplxEmbeddingService:
    """Async singleton service for Perplexity contextualized embeddings."""

    MODEL = "pplx-embed-context-v1-0.6b"
    DIMENSIONS = 1024
    MAX_BATCH_SIZE = 50  # Conservative batch limit

    def __init__(self):
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY is required for thread embeddings")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.perplexity.ai",
        )
        self._cache: Dict[str, List[float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    async def get_embedding(self, text: str) -> PplxEmbeddingResult:
        """Embed a single text. Returns cached result if available."""
        key = self._cache_key(text)
        if key in self._cache:
            self._cache_hits += 1
            return PplxEmbeddingResult(embedding=self._cache[key], cached=True)

        self._cache_misses += 1
        text = " ".join(text.split())  # Normalize whitespace

        try:
            response = await self.client.embeddings.create(
                model=self.MODEL,
                input=[text],
            )
            embedding = response.data[0].embedding
            self._cache[key] = embedding
            return PplxEmbeddingResult(embedding=embedding, cached=False)
        except Exception as e:
            logger.error("Perplexity embedding failed: %s", e)
            raise

    async def get_embeddings_batch(self, texts: List[str]) -> List[PplxEmbeddingResult]:
        """Embed multiple texts in a single API call. Uses cache where possible."""
        results: List[PplxEmbeddingResult] = [None] * len(texts)  # type: ignore
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        # Check cache first
        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                self._cache_hits += 1
                results[i] = PplxEmbeddingResult(embedding=self._cache[key], cached=True)
            else:
                self._cache_misses += 1
                uncached_indices.append(i)
                uncached_texts.append(" ".join(text.split()))

        # Batch embed uncached texts
        if uncached_texts:
            try:
                # Process in chunks of MAX_BATCH_SIZE
                for chunk_start in range(0, len(uncached_texts), self.MAX_BATCH_SIZE):
                    chunk = uncached_texts[chunk_start : chunk_start + self.MAX_BATCH_SIZE]
                    chunk_indices = uncached_indices[chunk_start : chunk_start + self.MAX_BATCH_SIZE]

                    response = await self.client.embeddings.create(
                        model=self.MODEL,
                        input=chunk,
                    )

                    for j, emb_data in enumerate(response.data):
                        idx = chunk_indices[j]
                        embedding = emb_data.embedding
                        self._cache[self._cache_key(texts[idx])] = embedding
                        results[idx] = PplxEmbeddingResult(embedding=embedding, cached=False)

            except Exception as e:
                logger.error("Perplexity batch embedding failed: %s", e)
                raise

        return results

    def get_cache_stats(self) -> dict:
        total = self._cache_hits + self._cache_misses
        return {
            "cache_size": len(self._cache),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": f"{self._cache_hits / total:.1%}" if total > 0 else "N/A",
        }


# Singleton
_service: PplxEmbeddingService | None = None


def get_pplx_embedding_service() -> PplxEmbeddingService:
    global _service
    if _service is None:
        _service = PplxEmbeddingService()
        logger.info("Initialized Perplexity embedding service (model=%s, dims=%d)",
                     PplxEmbeddingService.MODEL, PplxEmbeddingService.DIMENSIONS)
    return _service
