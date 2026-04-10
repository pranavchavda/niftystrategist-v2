"""Perplexity Embedding Service for cross-thread search.

Uses pplx-embed-v1-0.6b — 1024 dimensions, 32K token context, $0.004/1M tokens.
API requires base64_int8 encoding — we decode to float for pgvector storage.

Note: context-aware models (pplx-embed-context-v1-*) are listed in docs but
not yet available via API. Using standard model for now.
"""

import base64
import hashlib
import logging
import os
import struct
from dataclasses import dataclass
from typing import Dict, List

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://api.perplexity.ai/v1/embeddings"


@dataclass
class PplxEmbeddingResult:
    embedding: List[float]
    cached: bool = False


class PplxEmbeddingService:
    """Async singleton service for Perplexity embeddings."""

    MODEL = "pplx-embed-v1-0.6b"
    DIMENSIONS = 1024
    MAX_BATCH_SIZE = 50

    def __init__(self):
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY is required for thread embeddings")

        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache: Dict[str, List[float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _decode_int8_embedding(b64_str: str) -> List[float]:
        """Decode base64_int8 embedding to float list.

        Perplexity returns int8 values (-128 to 127). We normalize to
        roughly [-1, 1] by dividing by 127 for pgvector cosine similarity.
        """
        raw = base64.b64decode(b64_str)
        int8_values = struct.unpack(f"{len(raw)}b", raw)
        return [v / 127.0 for v in int8_values]

    async def _call_api(self, texts: List[str]) -> List[List[float]]:
        """Call Perplexity embedding API and return decoded float vectors."""
        response = await self._client.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.MODEL,
                "input": texts,
                "encoding_format": "base64_int8",
            },
        )
        response.raise_for_status()
        data = response.json()

        embeddings = []
        for item in sorted(data["data"], key=lambda x: x["index"]):
            embeddings.append(self._decode_int8_embedding(item["embedding"]))
        return embeddings

    async def get_embedding(self, text: str) -> PplxEmbeddingResult:
        """Embed a single text. Returns cached result if available."""
        key = self._cache_key(text)
        if key in self._cache:
            self._cache_hits += 1
            return PplxEmbeddingResult(embedding=self._cache[key], cached=True)

        self._cache_misses += 1
        text = " ".join(text.split())

        try:
            embeddings = await self._call_api([text])
            self._cache[key] = embeddings[0]
            return PplxEmbeddingResult(embedding=embeddings[0], cached=False)
        except Exception as e:
            logger.error("Perplexity embedding failed: %s", e)
            raise

    async def get_embeddings_batch(self, texts: List[str]) -> List[PplxEmbeddingResult]:
        """Embed multiple texts. Uses cache where possible."""
        results: List[PplxEmbeddingResult] = [None] * len(texts)  # type: ignore
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                self._cache_hits += 1
                results[i] = PplxEmbeddingResult(embedding=self._cache[key], cached=True)
            else:
                self._cache_misses += 1
                uncached_indices.append(i)
                uncached_texts.append(" ".join(text.split()))

        if uncached_texts:
            try:
                for chunk_start in range(0, len(uncached_texts), self.MAX_BATCH_SIZE):
                    chunk = uncached_texts[chunk_start : chunk_start + self.MAX_BATCH_SIZE]
                    chunk_indices = uncached_indices[chunk_start : chunk_start + self.MAX_BATCH_SIZE]

                    embeddings = await self._call_api(chunk)

                    for j, embedding in enumerate(embeddings):
                        idx = chunk_indices[j]
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
        logger.info(
            "Initialized Perplexity embedding service (model=%s, dims=%d)",
            PplxEmbeddingService.MODEL, PplxEmbeddingService.DIMENSIONS,
        )
    return _service
