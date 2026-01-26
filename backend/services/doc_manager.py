"""
Documentation Manager - DB-Primary Documentation System

Manages EspressoBot documentation with the database as the source of truth.
Provides CRUD operations, semantic search, and disk sync (export/import).

Architecture:
- `docs` table: Source of truth for full document content
- `doc_chunks` table: Derived chunks for semantic search
- Disk: Sync/transfer layer (export for backup, import for seeding)

Usage:
    from services.doc_manager import DocManager

    manager = DocManager()

    # CRUD operations
    doc = await manager.get_doc("graphql-operations/products/search.md")
    await manager.save_doc("path/to/doc.md", content, category="graphql")
    await manager.delete_doc("path/to/doc.md")
    docs = await manager.list_docs(category="graphql")

    # Sync operations
    await manager.export_to_disk()  # DB -> disk
    await manager.import_from_disk()  # disk -> DB

    # Search
    results = await manager.search("how to search products")
"""

import hashlib
import json
import logging
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, UTC
from dataclasses import dataclass

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from database.session import get_db_session

logger = logging.getLogger(__name__)


@dataclass
class Doc:
    """Represents a documentation entry"""
    id: int
    doc_path: str
    title: str
    content: str
    category: Optional[str] = None
    api_version: Optional[str] = None
    source: str = "disk"  # disk, manual, api
    metadata: Optional[Dict[str, Any]] = None
    last_updated: Optional[datetime] = None


@dataclass
class ExportResult:
    """Result of export operation"""
    success: bool
    exported_count: int
    errors: List[str]
    path: str


@dataclass
class ImportResult:
    """Result of import operation"""
    success: bool
    imported_count: int
    updated_count: int
    skipped_count: int
    errors: List[str]


class DocManager:
    """
    Manages documentation with DB as source of truth.

    Supports CRUD operations, semantic search, and disk sync.
    """

    def __init__(
        self,
        docs_dir: Optional[Path] = None,
        model_name: str = "text-embedding-3-large",
        use_openai: bool = True,
        api_key: Optional[str] = None
    ):
        """
        Initialize documentation manager.

        Args:
            docs_dir: Path to documentation directory (for import/export)
            model_name: Embedding model (default: text-embedding-3-large)
            use_openai: Use OpenAI API (True) or OpenRouter (False)
            api_key: API key (defaults to env var)
        """
        if docs_dir is None:
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
            self.embedding_dim = 3072
        else:
            self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
            if not self.api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable must be set")
            self.embedding_dim = 4096

        # HTTP client for embeddings (lazy init)
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(f"DocManager initialized with model: {model_name}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=10)
            )
        return self._client

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def get_doc(self, doc_path: str) -> Optional[Doc]:
        """
        Get a document by path.

        Args:
            doc_path: Relative path (e.g., "graphql-operations/products/search.md")

        Returns:
            Doc object or None if not found
        """
        async with get_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT id, doc_path, title, content, category, api_version,
                           source, metadata, last_updated
                    FROM docs
                    WHERE doc_path = :path
                """),
                {"path": doc_path}
            )
            row = result.fetchone()

            if not row:
                return None

            return Doc(
                id=row[0],
                doc_path=row[1],
                title=row[2],
                content=row[3],
                category=row[4],
                api_version=row[5],
                source=row[6] or "disk",
                metadata=row[7] if isinstance(row[7], dict) else (json.loads(row[7]) if row[7] else {}),
                last_updated=row[8]
            )

    async def get_doc_by_glob(self, pattern: str) -> List[Doc]:
        """
        Get documents matching a glob-like pattern.

        Args:
            pattern: Pattern with wildcards (e.g., "graphql-operations/products/*.md")

        Returns:
            List of matching Doc objects
        """
        # Convert glob pattern to SQL LIKE pattern
        sql_pattern = pattern.replace("*", "%").replace("?", "_")

        async with get_db_session() as session:
            result = await session.execute(
                text("""
                    SELECT id, doc_path, title, content, category, api_version,
                           source, metadata, last_updated
                    FROM docs
                    WHERE doc_path LIKE :pattern
                    ORDER BY doc_path
                """),
                {"pattern": sql_pattern}
            )
            rows = result.fetchall()

            return [
                Doc(
                    id=row[0],
                    doc_path=row[1],
                    title=row[2],
                    content=row[3],
                    category=row[4],
                    api_version=row[5],
                    source=row[6] or "disk",
                    metadata=row[7] if isinstance(row[7], dict) else (json.loads(row[7]) if row[7] else {}),
                    last_updated=row[8]
                )
                for row in rows
            ]

    async def save_doc(
        self,
        doc_path: str,
        content: str,
        title: Optional[str] = None,
        category: Optional[str] = None,
        api_version: Optional[str] = None,
        source: str = "manual",
        regenerate_chunks: bool = True
    ) -> Doc:
        """
        Save or update a document.

        Args:
            doc_path: Relative path for the document
            content: Full markdown content
            title: Document title (extracted from content if not provided)
            category: Document category
            api_version: API version (for Shopify docs)
            source: Origin of document (disk, manual, api)
            regenerate_chunks: Whether to regenerate search chunks

        Returns:
            Saved Doc object
        """
        # Extract title from content if not provided
        if not title:
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else Path(doc_path).stem

        # Infer category from path if not provided
        if not category:
            parts = Path(doc_path).parts
            if len(parts) >= 2:
                category = parts[0]

        async with get_db_session() as session:
            # Check if document exists
            result = await session.execute(
                text("SELECT id FROM docs WHERE doc_path = :path"),
                {"path": doc_path}
            )
            existing = result.fetchone()

            # Generate embedding for the content
            embedding = await self._generate_doc_embedding(content)
            halfvec_str = '[' + ','.join(str(v) for v in embedding) + ']'

            metadata = {
                "embedding_model": self.model_name,
                "embedding_dim": len(embedding),
                "updated_at": datetime.now(UTC).isoformat()
            }

            if existing:
                # Update existing document
                await session.execute(
                    text("""
                        UPDATE docs
                        SET title = :title,
                            content = :content,
                            category = :category,
                            api_version = :api_version,
                            source = :source,
                            embedding_halfvec = CAST(:embedding AS halfvec),
                            metadata = :metadata,
                            last_updated = NOW()
                        WHERE doc_path = :path
                    """),
                    {
                        "path": doc_path,
                        "title": title,
                        "content": content,
                        "category": category,
                        "api_version": api_version,
                        "source": source,
                        "embedding": halfvec_str,
                        "metadata": json.dumps(metadata)
                    }
                )
                doc_id = existing[0]
                logger.info(f"Updated document: {doc_path}")
            else:
                # Insert new document
                result = await session.execute(
                    text("""
                        INSERT INTO docs (doc_path, title, content, category, api_version,
                                         source, embedding_halfvec, metadata, last_updated)
                        VALUES (:path, :title, :content, :category, :api_version,
                               :source, CAST(:embedding AS halfvec), :metadata, NOW())
                        RETURNING id
                    """),
                    {
                        "path": doc_path,
                        "title": title,
                        "content": content,
                        "category": category,
                        "api_version": api_version,
                        "source": source,
                        "embedding": halfvec_str,
                        "metadata": json.dumps(metadata)
                    }
                )
                doc_id = result.fetchone()[0]
                logger.info(f"Created document: {doc_path}")

            await session.commit()

            # Regenerate chunks for search
            if regenerate_chunks:
                await self._regenerate_chunks(session, doc_path, content)
                await session.commit()

        return Doc(
            id=doc_id,
            doc_path=doc_path,
            title=title,
            content=content,
            category=category,
            api_version=api_version,
            source=source,
            metadata=metadata
        )

    async def delete_doc(self, doc_path: str) -> bool:
        """
        Delete a document and its chunks.

        Args:
            doc_path: Path of document to delete

        Returns:
            True if deleted, False if not found
        """
        async with get_db_session() as session:
            # Delete chunks first
            await session.execute(
                text("DELETE FROM doc_chunks WHERE file_path = :path"),
                {"path": doc_path}
            )

            # Delete document
            result = await session.execute(
                text("DELETE FROM docs WHERE doc_path = :path RETURNING id"),
                {"path": doc_path}
            )
            deleted = result.fetchone()

            await session.commit()

            if deleted:
                logger.info(f"Deleted document: {doc_path}")
                return True
            return False

    async def list_docs(
        self,
        category: Optional[str] = None,
        api_version: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Doc], int]:
        """
        List documents with optional filters.

        Args:
            category: Filter by category
            api_version: Filter by API version
            source: Filter by source (disk, manual, api)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (list of Docs, total count)
        """
        conditions = []
        params = {"limit": limit, "offset": offset}

        if category:
            conditions.append("category = :category")
            params["category"] = category
        if api_version:
            conditions.append("api_version = :api_version")
            params["api_version"] = api_version
        if source:
            conditions.append("source = :source")
            params["source"] = source

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with get_db_session() as session:
            # Get total count
            count_result = await session.execute(
                text(f"SELECT COUNT(*) FROM docs WHERE {where_clause}"),
                params
            )
            total = count_result.fetchone()[0]

            # Get documents
            result = await session.execute(
                text(f"""
                    SELECT id, doc_path, title, category, api_version, source,
                           metadata, last_updated
                    FROM docs
                    WHERE {where_clause}
                    ORDER BY doc_path
                    LIMIT :limit OFFSET :offset
                """),
                params
            )
            rows = result.fetchall()

            docs = [
                Doc(
                    id=row[0],
                    doc_path=row[1],
                    title=row[2],
                    content="",  # Don't load full content in list
                    category=row[3],
                    api_version=row[4],
                    source=row[5] or "disk",
                    metadata=row[6] if isinstance(row[6], dict) else (json.loads(row[6]) if row[6] else {}),
                    last_updated=row[7]
                )
                for row in rows
            ]

            return docs, total

    # =========================================================================
    # Export / Import Operations
    # =========================================================================

    async def export_to_disk(self, base_path: Optional[Path] = None) -> ExportResult:
        """
        Export all documents from DB to disk.

        Preserves directory structure based on doc_path.

        Args:
            base_path: Directory to export to (defaults to self.docs_dir)

        Returns:
            ExportResult with counts and any errors
        """
        if base_path is None:
            base_path = self.docs_dir

        base_path = Path(base_path)
        errors = []
        exported_count = 0

        async with get_db_session() as session:
            result = await session.execute(
                text("SELECT doc_path, content FROM docs ORDER BY doc_path")
            )
            rows = result.fetchall()

            for row in rows:
                doc_path, content = row[0], row[1]
                file_path = base_path / doc_path

                try:
                    # Create parent directories
                    file_path.parent.mkdir(parents=True, exist_ok=True)

                    # Write content
                    file_path.write_text(content, encoding='utf-8')
                    exported_count += 1
                    logger.debug(f"Exported: {doc_path}")

                except Exception as e:
                    error_msg = f"Error exporting {doc_path}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)

        logger.info(f"Export complete: {exported_count} documents to {base_path}")

        return ExportResult(
            success=len(errors) == 0,
            exported_count=exported_count,
            errors=errors,
            path=str(base_path)
        )

    async def import_from_disk(
        self,
        base_path: Optional[Path] = None,
        force: bool = False
    ) -> ImportResult:
        """
        Import documents from disk to DB.

        Args:
            base_path: Directory to import from (defaults to self.docs_dir)
            force: If True, overwrite existing documents even if unchanged

        Returns:
            ImportResult with counts and any errors
        """
        if base_path is None:
            base_path = self.docs_dir

        base_path = Path(base_path)

        if not base_path.exists():
            return ImportResult(
                success=False,
                imported_count=0,
                updated_count=0,
                skipped_count=0,
                errors=[f"Directory not found: {base_path}"]
            )

        errors = []
        imported_count = 0
        updated_count = 0
        skipped_count = 0

        # Find all markdown files
        md_files = list(base_path.rglob("*.md"))
        logger.info(f"Found {len(md_files)} markdown files in {base_path}")

        async with get_db_session() as session:
            for file_path in md_files:
                # Skip only metadata files (index/readme are useful navigation docs)
                if file_path.name.lower() == "metadata.md":
                    continue

                try:
                    # Calculate relative path
                    rel_path = str(file_path.relative_to(base_path))
                    content = file_path.read_text(encoding='utf-8')

                    # Check if exists and unchanged
                    result = await session.execute(
                        text("SELECT id, content FROM docs WHERE doc_path = :path"),
                        {"path": rel_path}
                    )
                    existing = result.fetchone()

                    if existing and not force:
                        if existing[1] == content:
                            skipped_count += 1
                            continue
                        updated_count += 1
                    else:
                        imported_count += 1

                    # Parse document
                    doc = self._parse_markdown_file(file_path, base_path)

                    # Save to DB (this handles insert/update)
                    await self._save_doc_internal(session, doc, source="disk")

                except Exception as e:
                    error_msg = f"Error importing {file_path}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            await session.commit()

        # Update metadata
        await self._update_metadata()

        logger.info(f"Import complete: {imported_count} new, {updated_count} updated, {skipped_count} skipped")

        return ImportResult(
            success=len(errors) == 0,
            imported_count=imported_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            errors=errors
        )

    # =========================================================================
    # Search Operations
    # =========================================================================

    async def search(
        self,
        query: str,
        api_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.35
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across documentation.

        Args:
            query: Search query
            api_filter: Filter by API name
            category_filter: Filter by category
            limit: Maximum results
            similarity_threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of search results with similarity scores
        """
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)
        halfvec_str = '[' + ','.join(str(v) for v in query_embedding) + ']'

        # Build SQL query
        sql = """
            SELECT
                id, doc_path, category, title, content, api_version, metadata,
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

        sql += """
            AND (1 - (embedding_halfvec <=> CAST(:embedding AS halfvec))) >= :threshold
            ORDER BY embedding_halfvec <=> CAST(:embedding AS halfvec)
            LIMIT :limit
        """
        params["threshold"] = similarity_threshold
        params["limit"] = limit

        async with get_db_session() as session:
            result = await session.execute(text(sql), params)
            rows = result.fetchall()

            return [
                {
                    "id": row[0],
                    "doc_path": row[1],
                    "category": row[2],
                    "title": row[3],
                    "content": row[4][:500] + "..." if len(row[4]) > 500 else row[4],
                    "api_version": row[5],
                    "metadata": row[6] if isinstance(row[6], dict) else (json.loads(row[6]) if row[6] else {}),
                    "similarity": float(row[7])
                }
                for row in rows
            ]

    # =========================================================================
    # Embedding Operations
    # =========================================================================

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if self.use_openai:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            response = await client.embeddings.create(
                model=self.model_name,
                input=text
            )
            return response.data[0].embedding
        else:
            client = await self._get_client()
            response = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://node.idrinkcoffee.info",
                    "X-Title": "EspressoBot DocManager",
                },
                json={"model": self.model_name, "input": text}
            )
            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code}")
            return response.json()["data"][0]["embedding"]

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if self.use_openai:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key)
            response = await client.embeddings.create(
                model=self.model_name,
                input=texts
            )
            return [item.embedding for item in response.data]
        else:
            client = await self._get_client()
            response = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://node.idrinkcoffee.info",
                    "X-Title": "EspressoBot DocManager",
                },
                json={"model": self.model_name, "input": texts}
            )
            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code}")
            return [item["embedding"] for item in response.json()["data"]]

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _generate_doc_embedding(self, content: str) -> List[float]:
        """Generate embedding for document content."""
        # Chunk the content
        chunks = self._chunk_text(content)

        # Generate embeddings for chunks
        try:
            embeddings = await self.generate_embeddings_batch(chunks)
        except Exception as e:
            logger.warning(f"Batch embedding failed, trying single: {e}")
            text = content[:8000]
            embedding = await self.generate_embedding(text)
            return embedding

        # Average the embeddings
        import numpy as np
        return np.mean(embeddings, axis=0).tolist()

    def _chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            if end < len(text):
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

            start = end - overlap

        return chunks

    def _parse_markdown_file(self, file_path: Path, base_path: Path) -> Dict[str, Any]:
        """Parse a markdown file and extract metadata."""
        content = file_path.read_text(encoding='utf-8')

        # Extract title
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else file_path.stem

        # Determine category and API from path
        relative_path = file_path.relative_to(base_path)
        parts = relative_path.parts

        category = "general"
        api_version = None

        if len(parts) >= 2:
            category = parts[0]
            if len(parts) > 2:
                api_version = parts[0]

        return {
            "title": title,
            "content": content,
            "category": category,
            "api_version": api_version,
            "doc_path": str(relative_path),
            "file_path": str(file_path)
        }

    async def _save_doc_internal(self, session: AsyncSession, doc: Dict[str, Any], source: str = "disk"):
        """Internal save method (within existing session)."""
        # Generate embedding
        embedding = await self._generate_doc_embedding(doc["content"])
        halfvec_str = '[' + ','.join(str(v) for v in embedding) + ']'

        metadata = {
            "file_path": doc.get("file_path"),
            "embedding_model": self.model_name,
            "embedding_dim": len(embedding),
            "indexed_at": datetime.now(UTC).isoformat()
        }

        # Check if exists
        result = await session.execute(
            text("SELECT id FROM docs WHERE doc_path = :path"),
            {"path": doc["doc_path"]}
        )
        existing = result.fetchone()

        if existing:
            await session.execute(
                text("""
                    UPDATE docs
                    SET title = :title, content = :content, category = :category,
                        api_version = :api_version, source = :source,
                        embedding_halfvec = CAST(:embedding AS halfvec),
                        metadata = :metadata, last_updated = NOW()
                    WHERE doc_path = :path
                """),
                {
                    "path": doc["doc_path"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "category": doc["category"],
                    "api_version": doc["api_version"],
                    "source": source,
                    "embedding": halfvec_str,
                    "metadata": json.dumps(metadata)
                }
            )
        else:
            await session.execute(
                text("""
                    INSERT INTO docs (doc_path, title, content, category, api_version,
                                     source, embedding_halfvec, metadata, last_updated)
                    VALUES (:path, :title, :content, :category, :api_version,
                           :source, CAST(:embedding AS halfvec), :metadata, NOW())
                """),
                {
                    "path": doc["doc_path"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "category": doc["category"],
                    "api_version": doc["api_version"],
                    "source": source,
                    "embedding": halfvec_str,
                    "metadata": json.dumps(metadata)
                }
            )

        # Regenerate chunks
        await self._regenerate_chunks(session, doc["doc_path"], doc["content"])

    async def _regenerate_chunks(self, session: AsyncSession, doc_path: str, content: str):
        """Regenerate search chunks for a document."""
        # Delete existing chunks
        await session.execute(
            text("DELETE FROM doc_chunks WHERE file_path = :path"),
            {"path": doc_path}
        )

        # Create new chunks
        chunks = self._chunk_text(content, chunk_size=800, overlap=100)

        try:
            embeddings = await self.generate_embeddings_batch(chunks)
        except Exception as e:
            logger.error(f"Failed to generate chunk embeddings: {e}")
            return

        # Insert chunks
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            halfvec_str = '[' + ','.join(str(v) for v in embedding) + ']'

            await session.execute(
                text("""
                    INSERT INTO doc_chunks
                    (file_path, chunk_index, chunk_text, chunk_tokens, embedding_halfvec, created_at, updated_at)
                    VALUES (:path, :index, :text, :tokens, CAST(:embedding AS halfvec), NOW(), NOW())
                """),
                {
                    "path": doc_path,
                    "index": i,
                    "text": chunk,
                    "tokens": len(chunk.split()),
                    "embedding": halfvec_str
                }
            )

    async def _update_metadata(self):
        """Update docs_metadata table."""
        async with get_db_session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM docs"))
            total_docs = result.fetchone()[0]

            result = await session.execute(
                text("SELECT api_version, COUNT(*) FROM docs GROUP BY api_version")
            )
            api_breakdown = {row[0]: row[1] for row in result.fetchall()}

            for api_name, doc_count in api_breakdown.items():
                if api_name:
                    await session.execute(
                        text("""
                            INSERT INTO docs_metadata (api_name, version, last_checked, last_updated, total_docs, metadata)
                            VALUES (:api_name, '2025-01', NOW(), NOW(), :count, :metadata)
                            ON CONFLICT (api_name) DO UPDATE SET
                                last_checked = NOW(),
                                last_updated = NOW(),
                                total_docs = :count,
                                metadata = :metadata
                        """),
                        {
                            "api_name": api_name,
                            "count": doc_count,
                            "metadata": json.dumps({
                                "last_update": datetime.now(UTC).isoformat(),
                                "embedding_model": self.model_name
                            })
                        }
                    )

            await session.commit()
            logger.info(f"Updated metadata: {total_docs} total docs")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get documentation statistics."""
        async with get_db_session() as session:
            # Total docs
            result = await session.execute(text("SELECT COUNT(*) FROM docs"))
            total_docs = result.fetchone()[0]

            # Total chunks
            result = await session.execute(text("SELECT COUNT(*) FROM doc_chunks"))
            total_chunks = result.fetchone()[0]

            # By category
            result = await session.execute(
                text("SELECT category, COUNT(*) FROM docs GROUP BY category ORDER BY COUNT(*) DESC")
            )
            by_category = {row[0]: row[1] for row in result.fetchall()}

            # By source
            result = await session.execute(
                text("SELECT COALESCE(source, 'disk'), COUNT(*) FROM docs GROUP BY source")
            )
            by_source = {row[0]: row[1] for row in result.fetchall()}

            return {
                "total_docs": total_docs,
                "total_chunks": total_chunks,
                "by_category": by_category,
                "by_source": by_source
            }

    async def build_file_tree(self) -> Dict[str, Any]:
        """
        Build a file tree structure from documents in DB.

        Returns:
            Hierarchical file tree structure
        """
        async with get_db_session() as session:
            result = await session.execute(
                text("SELECT doc_path, title FROM docs ORDER BY doc_path")
            )
            rows = result.fetchall()

        # Build tree structure
        root = {"name": "docs", "path": "", "type": "folder", "children": []}

        for row in rows:
            doc_path, title = row[0], row[1]
            parts = Path(doc_path).parts

            current = root
            for i, part in enumerate(parts):
                is_file = i == len(parts) - 1

                # Find or create child
                child = None
                for c in current.get("children", []):
                    if c["name"] == part:
                        child = c
                        break

                if child is None:
                    path_so_far = "/".join(parts[:i+1])
                    child = {
                        "name": part,
                        "path": path_so_far,
                        "type": "file" if is_file else "folder",
                    }
                    if not is_file:
                        child["children"] = []
                    current.setdefault("children", []).append(child)

                current = child

        return root


# Backwards compatibility alias
DocIndexer = DocManager


async def main():
    """CLI entry point."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description="Documentation Manager")
    parser.add_argument("action", choices=["import", "export", "stats", "search"],
                       help="Action to perform")
    parser.add_argument("--force", action="store_true", help="Force overwrite")
    parser.add_argument("--query", type=str, help="Search query")
    parser.add_argument("--docs-dir", type=Path, help="Documentation directory")

    args = parser.parse_args()

    manager = DocManager(docs_dir=args.docs_dir)

    try:
        if args.action == "import":
            result = await manager.import_from_disk(force=args.force)
            print(f"Imported: {result.imported_count}, Updated: {result.updated_count}, Skipped: {result.skipped_count}")
            if result.errors:
                print(f"Errors: {result.errors}")

        elif args.action == "export":
            result = await manager.export_to_disk()
            print(f"Exported: {result.exported_count} documents to {result.path}")
            if result.errors:
                print(f"Errors: {result.errors}")

        elif args.action == "stats":
            stats = await manager.get_stats()
            print(json.dumps(stats, indent=2))

        elif args.action == "search":
            if not args.query:
                print("--query required for search")
                return
            results = await manager.search(args.query)
            for r in results:
                print(f"\n[{r['similarity']:.2%}] {r['title']}")
                print(f"  Path: {r['doc_path']}")
                print(f"  {r['content'][:200]}...")

    finally:
        await manager.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
