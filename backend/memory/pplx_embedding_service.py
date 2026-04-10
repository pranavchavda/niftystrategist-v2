"""Perplexity Contextualized Embedding Service for cross-thread search.

Uses pplx-embed-context-v1-0.6b — contextualized embeddings optimized
for document chunks that share context (conversation turns from the same thread).

1024 dimensions, 32K token context per document, $0.008/1M tokens.
API: POST https://api.perplexity.ai/v1/contextualizedembeddings

The contextualized endpoint takes nested arrays: [[chunk1, chunk2, ...]]
where each inner array is a "document" — chunks within the same document
get embeddings that are aware of their siblings, improving retrieval quality.
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

# Contextualized embeddings use a separate endpoint from standard embeddings
CONTEXT_API_URL = "https://api.perplexity.ai/v1/contextualizedembeddings"
# Standard embeddings endpoint (fallback for single-query search)
STANDARD_API_URL = "https://api.perplexity.ai/v1/embeddings"


@dataclass
class PplxEmbeddingResult:
    embedding: List[float]
    cached: bool = False


class PplxEmbeddingService:
    """Async singleton service for Perplexity contextualized embeddings."""

    CONTEXT_MODEL = "pplx-embed-context-v1-0.6b"
    STANDARD_MODEL = "pplx-embed-v1-0.6b"
    DIMENSIONS = 1024
    MAX_CHUNKS_PER_DOC = 500  # API allows up to 16,000 total chunks

    def __init__(self):
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY is required for thread embeddings")

        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
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

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy-create httpx client in the current event loop."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _call_context_api(self, documents: List[List[str]]) -> List[List[List[float]]]:
        """Call Perplexity contextualized embedding API.

        Args:
            documents: Nested array — each inner array is chunks from one document.
                      e.g., [[turn1, turn2, turn3]] for one thread's turns.

        Returns:
            Nested list matching input structure: [[emb1, emb2, emb3]]
        """
        response = await self._get_client().post(
            CONTEXT_API_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.CONTEXT_MODEL,
                "input": documents,
                "encoding_format": "base64_int8",
            },
        )
        response.raise_for_status()
        data = response.json()

        # Response data is flat list of embeddings with document_index + chunk_index
        # Reconstruct nested structure
        result: Dict[int, Dict[int, List[float]]] = {}
        for item in data["data"]:
            doc_idx = item.get("document_index", 0)
            chunk_idx = item.get("index", item.get("chunk_index", 0))
            result.setdefault(doc_idx, {})[chunk_idx] = self._decode_int8_embedding(item["embedding"])

        # Convert to ordered nested list
        nested = []
        for doc_idx in sorted(result.keys()):
            chunks = result[doc_idx]
            nested.append([chunks[i] for i in sorted(chunks.keys())])
        return nested

    async def _call_standard_api(self, texts: List[str]) -> List[List[float]]:
        """Call standard (non-contextualized) embedding API for search queries."""
        response = await self._get_client().post(
            STANDARD_API_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.STANDARD_MODEL,
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
        """Embed a single text (for search queries). Uses standard endpoint.

        Search queries don't need contextualization — they're standalone.
        """
        key = self._cache_key(text)
        if key in self._cache:
            self._cache_hits += 1
            return PplxEmbeddingResult(embedding=self._cache[key], cached=True)

        self._cache_misses += 1
        text = " ".join(text.split())

        try:
            embeddings = await self._call_standard_api([text])
            self._cache[key] = embeddings[0]
            return PplxEmbeddingResult(embedding=embeddings[0], cached=False)
        except Exception as e:
            logger.error("Perplexity embedding failed: %s", e)
            raise

    async def get_embeddings_batch(self, texts: List[str]) -> List[PplxEmbeddingResult]:
        """Embed multiple texts from the same thread using contextualized API.

        All texts are sent as chunks of a single "document" so the model
        produces context-aware embeddings — each turn's embedding considers
        the surrounding conversation.
        """
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
                # Send all turns as one document for contextualized embedding
                for chunk_start in range(0, len(uncached_texts), self.MAX_CHUNKS_PER_DOC):
                    chunk = uncached_texts[chunk_start : chunk_start + self.MAX_CHUNKS_PER_DOC]
                    chunk_indices = uncached_indices[chunk_start : chunk_start + self.MAX_CHUNKS_PER_DOC]

                    # Wrap as single document: [[turn1, turn2, ...]]
                    nested_result = await self._call_context_api([chunk])
                    doc_embeddings = nested_result[0]  # First (only) document

                    for j, embedding in enumerate(doc_embeddings):
                        idx = chunk_indices[j]
                        self._cache[self._cache_key(texts[idx])] = embedding
                        results[idx] = PplxEmbeddingResult(embedding=embedding, cached=False)

            except Exception as e:
                logger.error("Perplexity contextualized batch embedding failed: %s", e)
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
            "Initialized Perplexity embedding service (context=%s, search=%s, dims=%d)",
            PplxEmbeddingService.CONTEXT_MODEL,
            PplxEmbeddingService.STANDARD_MODEL,
            PplxEmbeddingService.DIMENSIONS,
        )
    return _service
