"""
Shopify Documentation Indexer

Indexes locally downloaded Shopify documentation for fast semantic search.
Uses Qwen 3 Embedding 8B via OpenRouter for high-quality, cost-effective embeddings.

Usage:
    from services.doc_indexer import DocIndexer
    indexer = DocIndexer()
    await indexer.index_all()
"""

import hashlib
import json
import logging
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text

from database.session import get_db_session

logger = logging.getLogger(__name__)


class DocIndexer:
    """Indexes Shopify documentation with semantic embeddings"""

    def __init__(
        self,
        docs_dir: Optional[Path] = None,
        model_name: str = "text-embedding-3-large",
        use_openai: bool = True,
        api_key: Optional[str] = None
    ):
        """
        Initialize documentation indexer.

        Args:
            docs_dir: Path to shopify-api documentation directory
            model_name: Embedding model (default: text-embedding-3-large for OpenAI)
            use_openai: Use OpenAI API (default: True), False for OpenRouter
            api_key: API key (defaults to OPENAI_API_KEY or OPENROUTER_API_KEY env var)
        """
        if docs_dir is None:
            # Default to backend/docs (includes shopifyql and other documentation)
            backend_dir = Path(__file__).parent.parent
            docs_dir = backend_dir / "docs"

        self.docs_dir = docs_dir
        self.model_name = model_name
        self.use_openai = use_openai

        # Get API key from environment
        if use_openai:
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY environment variable must be set")
            self.embedding_dim = 3072  # text-embedding-3-large
        else:
            self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
            if not self.api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable must be set")
            self.embedding_dim = 4096  # qwen/qwen3-embedding-8b

        # Create HTTP client for embeddings
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=10)
        )

        logger.info(f"DocIndexer initialized with model: {model_name} ({'OpenAI' if use_openai else 'OpenRouter'})")
        logger.info(f"Documentation directory: {self.docs_dir}")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI or OpenRouter API.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        if self.use_openai:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)

            response = await client.embeddings.create(
                model=self.model_name,
                input=text
            )
            return response.data[0].embedding
        else:
            # OpenRouter
            response = await self.client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://node.idrinkcoffee.info",
                    "X-Title": "EspressoBot Documentation Indexer",
                },
                json={
                    "model": self.model_name,
                    "input": text,
                }
            )

            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

            data = response.json()
            return data["data"][0]["embedding"]

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if self.use_openai:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)

            response = await client.embeddings.create(
                model=self.model_name,
                input=texts
            )
            return [item.embedding for item in response.data]
        else:
            # OpenRouter supports batch embeddings
            response = await self.client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://node.idrinkcoffee.info",
                    "X-Title": "EspressoBot Documentation Indexer",
                },
                json={
                    "model": self.model_name,
                    "input": texts,  # Send all texts at once
                }
            )

            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

            data = response.json()
            return [item["embedding"] for item in data["data"]]

    def chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks for better semantic coverage.

        Args:
            text: Text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near the end
                sentence_end = max(
                    text.rfind('. ', start, end),
                    text.rfind('! ', start, end),
                    text.rfind('? ', start, end),
                    text.rfind('\n', start, end)
                )

                if sentence_end > start + chunk_size // 2:
                    end = sentence_end + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - overlap

        return chunks

    def parse_markdown_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a markdown file and extract metadata.

        Args:
            file_path: Path to markdown file

        Returns:
            Dictionary with title, content, category, api_version
        """
        content = file_path.read_text(encoding='utf-8')

        # Extract title from first heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else file_path.stem

        # Determine category and API from path
        relative_path = file_path.relative_to(self.docs_dir)
        parts = relative_path.parts

        category = "general"
        api_version = None

        if len(parts) >= 2:
            api_name = parts[0]  # e.g., "admin", "storefront-graphql", "liquid"
            category = parts[1] if len(parts) > 2 else parts[1].replace('.md', '')

            # Try to extract API version from metadata
            if (self.docs_dir / api_name / "metadata.json").exists():
                metadata = json.loads((self.docs_dir / api_name / "metadata.json").read_text())
                api_version = metadata.get("api_name", api_name)

        return {
            "title": title,
            "content": content,
            "category": category,
            "api_version": api_version,
            "doc_path": str(relative_path),
            "file_path": str(file_path)
        }

    async def index_document(self, session: AsyncSession, doc: Dict[str, Any]):
        """
        Index a single document with embeddings.

        Args:
            session: Database session
            doc: Document metadata and content
        """
        # Check if document already exists
        result = await session.execute(
            text("SELECT id, content FROM docs WHERE doc_path = :path"),
            {"path": doc["doc_path"]}
        )
        existing = result.fetchone()

        # Check if content has changed
        if existing:
            existing_content = existing[1]
            if existing_content == doc["content"]:
                logger.debug(f"  Skipping unchanged document: {doc['doc_path']}")
                return

            # Content changed, delete old entry
            await session.execute(
                text("DELETE FROM docs WHERE id = :id"),
                {"id": existing[0]}
            )
            logger.info(f"  Updated document: {doc['doc_path']}")

        # Create embeddings for text chunks
        chunks = self.chunk_text(doc["content"])

        # Generate embeddings in batch for efficiency
        try:
            embeddings = await self.generate_embeddings_batch(chunks)
        except Exception as e:
            logger.error(f"  Error generating embeddings: {e}")
            # Fallback to single embedding of full content
            try:
                full_text = doc["content"][:8000]  # Limit to 8K chars
                embedding = await self.generate_embedding(full_text)
                embeddings = [embedding]
                chunks = [full_text]
            except Exception as e2:
                logger.error(f"  Fallback embedding failed: {e2}")
                return

        # Use average embedding (can be improved with chunk-level storage later)
        import numpy as np
        avg_embedding = np.mean(embeddings, axis=0).tolist()

        # Insert into database
        await session.execute(
            text("""
                INSERT INTO docs (doc_path, category, title, content, embedding, api_version, metadata)
                VALUES (:doc_path, :category, :title, :content, :embedding, :api_version, :metadata)
            """),
            {
                "doc_path": doc["doc_path"],
                "category": doc["category"],
                "title": doc["title"],
                "content": doc["content"],
                "embedding": json.dumps(avg_embedding),
                "api_version": doc["api_version"],
                "metadata": json.dumps({
                    "file_path": doc["file_path"],
                    "chunk_count": len(chunks),
                    "embedding_model": self.model_name,
                    "embedding_dim": len(avg_embedding),
                    "indexed_at": datetime.datetime.now(datetime.UTC).isoformat()
                })
            }
        )

        logger.info(f"  Indexed: {doc['title']} ({len(chunks)} chunks, {len(avg_embedding)} dims)")

    async def index_all(self, force: bool = False):
        """
        Index all Shopify documentation files.

        Args:
            force: If True, re-index all documents even if unchanged
        """
        if not self.docs_dir.exists():
            logger.warning(f"Documentation directory not found: {self.docs_dir}")
            logger.warning("Run download_shopify_docs.py first to download documentation")
            return

        logger.info(f"🔍 Indexing Shopify documentation from {self.docs_dir}")

        # Find all markdown files
        md_files = list(self.docs_dir.rglob("*.md"))
        logger.info(f"   Found {len(md_files)} markdown files")

        if force:
            logger.info("   Force mode: re-indexing all documents")

        indexed_count = 0
        skipped_count = 0
        error_count = 0

        async with get_db_session() as session:
            for md_file in md_files:
                try:
                    # Skip metadata files and index files
                    if md_file.name.lower() in ["index.md", "readme.md", "metadata.md"]:
                        continue

                    # Parse and index
                    doc = self.parse_markdown_file(md_file)
                    await self.index_document(session, doc)
                    indexed_count += 1

                except Exception as e:
                    logger.error(f"  Error indexing {md_file}: {e}")
                    error_count += 1

            # Commit all changes
            await session.commit()

        # Update metadata table
        await self.update_index_metadata()

        # Close HTTP client
        await self.client.aclose()

        logger.info(f"\n✅ Indexing complete!")
        logger.info(f"   Indexed: {indexed_count} documents")
        logger.info(f"   Skipped: {skipped_count} unchanged documents")
        logger.info(f"   Errors: {error_count}")

    async def update_index_metadata(self):
        """Update docs_metadata table with index statistics"""
        async with get_db_session() as session:
            # Calculate content hash
            content_hash = self._calculate_content_hash()

            # Count total docs
            result = await session.execute(text("SELECT COUNT(*) FROM docs"))
            total_docs = result.fetchone()[0]

            # Get API breakdown
            result = await session.execute(
                text("SELECT api_version, COUNT(*) FROM docs GROUP BY api_version")
            )
            api_breakdown = {row[0]: row[1] for row in result.fetchall()}

            # Update or insert metadata for each API
            for api_name, doc_count in api_breakdown.items():
                if api_name:
                    await session.execute(
                        text("""
                            INSERT INTO docs_metadata (api_name, version, last_checked, last_updated, content_hash, total_docs, metadata)
                            VALUES (:api_name, '2025-07', NOW(), NOW(), :hash, :count, :metadata)
                            ON CONFLICT (api_name)
                            DO UPDATE SET
                                last_checked = NOW(),
                                last_updated = NOW(),
                                content_hash = :hash,
                                total_docs = :count,
                                metadata = :metadata
                        """),
                        {
                            "api_name": api_name,
                            "hash": content_hash,
                            "count": doc_count,
                            "metadata": json.dumps({
                                "last_index_run": datetime.datetime.now(datetime.UTC).isoformat(),
                                "embedding_model": self.model_name
                            })
                        }
                    )

            await session.commit()
            logger.info(f"📊 Updated metadata: {total_docs} total docs across {len(api_breakdown)} APIs")

    def _calculate_content_hash(self) -> str:
        """Calculate SHA256 hash of all documentation content"""
        if not self.docs_dir.exists():
            return ""

        hasher = hashlib.sha256()
        for file_path in sorted(self.docs_dir.rglob("*.md")):
            if file_path.name.lower() not in ["index.md", "readme.md"]:
                hasher.update(file_path.read_bytes())

        return hasher.hexdigest()

    async def search(
        self,
        query: str,
        api_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across indexed documentation using pgvector cosine distance.

        Args:
            query: Search query
            api_filter: Filter by API name (e.g., "admin", "storefront-graphql")
            category_filter: Filter by category (e.g., "schemas", "operations")
            limit: Maximum number of results

        Returns:
            List of search results with similarity scores
        """
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)

        # Convert to halfvec format
        halfvec_str = '[' + ','.join(str(v) for v in query_embedding) + ']'

        # Build SQL query using pgvector operators with filters
        sql = """
            SELECT
                id,
                doc_path,
                category,
                title,
                content,
                api_version,
                metadata,
                (1 - (embedding_halfvec <=> CAST(:embedding AS halfvec))) AS similarity
            FROM docs
            WHERE embedding_halfvec IS NOT NULL
        """
        params = {"embedding": halfvec_str}

        if api_filter:
            sql += " AND api_version = :api_filter"
            params["api_filter"] = api_filter

        if category_filter:
            sql += " AND category = :category_filter"
            params["category_filter"] = category_filter

        sql += " ORDER BY embedding_halfvec <=> CAST(:embedding AS halfvec) LIMIT :limit"
        params["limit"] = limit

        async with get_db_session() as session:
            result = await session.execute(text(sql), params)
            rows = result.fetchall()

            results = []
            for row in rows:
                # Handle metadata (may already be deserialized)
                metadata = row[6] if isinstance(row[6], dict) else (json.loads(row[6]) if row[6] else {})

                results.append({
                    "id": row[0],
                    "doc_path": row[1],
                    "category": row[2],
                    "title": row[3],
                    "content": row[4][:500] + "..." if len(row[4]) > 500 else row[4],
                    "api_version": row[5],
                    "metadata": metadata,
                    "similarity": float(row[7])
                })

            return results


async def main():
    """CLI entry point for indexing"""
    import argparse

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description="Index Shopify documentation")
    parser.add_argument("--force", action="store_true", help="Force re-index all documents")
    parser.add_argument("--docs-dir", type=Path, help="Documentation directory")
    parser.add_argument("--model", default="text-embedding-3-large", help="Embedding model to use")

    args = parser.parse_args()

    indexer = DocIndexer(docs_dir=args.docs_dir, model_name=args.model, use_openai=True)
    await indexer.index_all(force=args.force)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
