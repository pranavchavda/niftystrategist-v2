"""
Unified Documentation Indexer

Handles indexing for both:
- Internal business documentation (backend/docs/)
- Shopify API documentation (backend/docs/shopify-api/)

Uses Qwen 3 Embedding 8B (4096 dimensions) via OpenRouter for both.
"""

import hashlib
import json
import logging
import os
import re
import sys
import tiktoken
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database.session import get_db_session

logger = logging.getLogger(__name__)


class UnifiedDocsIndexer:
    """
    Unified indexer for all documentation with Qwen embeddings.

    Handles both internal business docs and Shopify API docs with:
    - Smart markdown chunking
    - Qwen 3 Embedding 8B (4096-dim) via OpenRouter
    - PostgreSQL storage with pgvector support
    """

    def __init__(
        self,
        docs_dir: Optional[Path] = None,
        doc_type: Literal["internal", "shopify"] = "internal",
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        model_name: str = "text-embedding-3-large",
        use_openai: bool = True,
        api_key: Optional[str] = None
    ):
        """
        Initialize unified documentation indexer.

        Args:
            docs_dir: Path to documentation directory
            doc_type: Type of docs to index ("internal" or "shopify")
            chunk_size: Target chunk size in tokens (default 800)
            chunk_overlap: Overlap between chunks in tokens (default 100)
            model_name: Embedding model (default: text-embedding-3-large)
            use_openai: Use OpenAI API (True) or OpenRouter (False)
            api_key: API key (defaults to OPENAI_API_KEY or OPENROUTER_API_KEY env var)
        """
        if docs_dir is None:
            backend_dir = Path(__file__).parent.parent
            if doc_type == "shopify":
                docs_dir = backend_dir / "docs" / "shopify-api"
            else:
                docs_dir = backend_dir / "docs"

        self.docs_dir = docs_dir
        self.doc_type = doc_type
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
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

        # Create HTTP client for embeddings (only for OpenRouter)
        if not use_openai:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=10)
            )

        # Tokenizer for counting tokens
        self.encoding = tiktoken.encoding_for_model("gpt-4")

        logger.info(f"UnifiedDocsIndexer initialized:")
        logger.info(f"  Type: {doc_type}")
        logger.info(f"  Directory: {self.docs_dir}")
        logger.info(f"  Model: {model_name}")
        logger.info(f"  Embedding dim: {self.embedding_dim}")
        logger.info(f"  Chunk size: {chunk_size} tokens")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI or OpenRouter API.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats (3072 or 4096 dimensions)
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
            response = await self.client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://node.idrinkcoffee.info",
                    "X-Title": "EspressoBot Documentation Indexer",
                },
                json={
                    "model": self.model_name,
                    "input": texts,
                }
            )

            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

            data = response.json()
            return [item["embedding"] for item in data["data"]]

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        return len(self.encoding.encode(text))

    def _parse_sections(self, content: str) -> List[dict]:
        """
        Parse markdown into sections based on headings.

        Returns:
            List of dicts with 'heading' and 'text' keys
        """
        sections = []
        current_heading = ""
        current_text = []

        lines = content.split('\n')
        heading_stack = []  # Track heading hierarchy

        for line in lines:
            # Check if line is a heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)

            if heading_match:
                # Save previous section
                if current_text:
                    sections.append({
                        'heading': current_heading,
                        'text': '\n'.join(current_text).strip()
                    })
                    current_text = []

                # Update heading context
                level = len(heading_match.group(1))
                heading_title = heading_match.group(2)

                # Update stack to current level
                heading_stack = heading_stack[:level-1]
                heading_stack.append(heading_title)

                current_heading = ' / '.join(heading_stack)
                current_text = [line]  # Include heading in text
            else:
                current_text.append(line)

        # Add final section
        if current_text:
            sections.append({
                'heading': current_heading,
                'text': '\n'.join(current_text).strip()
            })

        return sections

    def chunk_markdown(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Chunk markdown content using semantic splitting.

        Strategy:
        1. Split by markdown headings (preserve context)
        2. Combine consecutive small sections until reaching chunk_size target
        3. If section too large, split by paragraphs with overlap
        4. Preserve heading hierarchy as metadata

        Args:
            content: Markdown content
            file_path: Relative file path for reference

        Returns:
            List of chunk dicts with keys: chunk_text, chunk_tokens, heading_context, chunk_index
        """
        chunks = []
        chunk_index = 0

        # Parse content into sections based on headings
        sections = self._parse_sections(content)

        # Combine small sections to reach target chunk_size
        i = 0
        while i < len(sections):
            section = sections[i]
            heading, text = section['heading'], section['text']
            tokens = self._count_tokens(text)

            # If section is much larger than chunk_size, split it
            if tokens > self.chunk_size * 1.5:
                # Section too large, split by paragraphs with overlap
                sub_chunks = self._split_by_paragraphs(text, heading)
                for sub_chunk_text, sub_tokens in sub_chunks:
                    chunks.append({
                        'file_path': file_path,
                        'chunk_index': chunk_index,
                        'chunk_text': sub_chunk_text,
                        'heading_context': heading,
                        'chunk_tokens': sub_tokens
                    })
                    chunk_index += 1
                i += 1
            else:
                # Try to combine with following sections to reach target size
                combined_text = [text]
                combined_tokens = tokens
                combined_heading = heading
                j = i + 1

                # Keep adding sections until we reach chunk_size or run out
                while j < len(sections) and combined_tokens < self.chunk_size:
                    next_section = sections[j]
                    next_tokens = self._count_tokens(next_section['text'])

                    # Stop if adding would exceed chunk_size significantly
                    if combined_tokens + next_tokens > self.chunk_size * 1.2:
                        break

                    combined_text.append(next_section['text'])
                    combined_tokens += next_tokens
                    j += 1

                # Create chunk from combined sections
                chunk_text = '\n\n'.join(combined_text)
                chunks.append({
                    'file_path': file_path,
                    'chunk_index': chunk_index,
                    'chunk_text': chunk_text,
                    'heading_context': combined_heading,
                    'chunk_tokens': combined_tokens
                })
                chunk_index += 1
                i = j  # Continue from next uncombined section

        logger.debug(f"Created {len(chunks)} chunks from {file_path}")
        return chunks

    def _split_by_paragraphs(self, text: str, heading: str) -> List[tuple[str, int]]:
        """
        Split large text by paragraphs with overlap.

        Args:
            text: Text to split
            heading: Heading context

        Returns:
            List of (chunk_text, token_count) tuples
        """
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0

        for i, para in enumerate(paragraphs):
            para_tokens = self._count_tokens(para)

            if current_tokens + para_tokens <= self.chunk_size:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                # Save current chunk
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append((chunk_text, current_tokens))

                    # Start new chunk with overlap (include last paragraph)
                    overlap_paras = []
                    overlap_tokens = 0

                    for j in range(len(current_chunk) - 1, -1, -1):
                        prev_para = current_chunk[j]
                        prev_tokens = self._count_tokens(prev_para)

                        if overlap_tokens + prev_tokens <= self.chunk_overlap:
                            overlap_paras.insert(0, prev_para)
                            overlap_tokens += prev_tokens
                        else:
                            break

                    current_chunk = overlap_paras + [para]
                    current_tokens = overlap_tokens + para_tokens
                else:
                    # Single paragraph exceeds chunk size, include anyway
                    current_chunk = [para]
                    current_tokens = para_tokens

        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append((chunk_text, current_tokens))

        return chunks

    async def index_all(self, force: bool = False):
        """
        Index all documentation files.

        Args:
            force: If True, re-index all documents even if unchanged
        """
        if not self.docs_dir.exists():
            logger.warning(f"Documentation directory not found: {self.docs_dir}")
            return

        logger.info(f"🔍 Indexing {self.doc_type} documentation from {self.docs_dir}")

        # Find all markdown files
        md_files = list(self.docs_dir.rglob("*.md"))

        # Filter out index/readme files for Shopify docs
        if self.doc_type == "shopify":
            md_files = [f for f in md_files if f.name.lower() not in ["index.md", "readme.md", "metadata.md"]]

        logger.info(f"   Found {len(md_files)} markdown files")

        indexed_count = 0
        error_count = 0

        async with get_db_session() as session:
            for md_file in md_files:
                try:
                    # Read file
                    content = md_file.read_text(encoding='utf-8')

                    # Get relative path
                    relative_path = str(md_file.relative_to(self.docs_dir.parent))

                    # Chunk the file
                    chunks = self.chunk_markdown(content, relative_path)

                    # Generate embeddings
                    texts = [chunk['chunk_text'] for chunk in chunks]
                    embeddings = await self.generate_embeddings_batch(texts)

                    # Store in database
                    await self._store_chunks(session, chunks, embeddings, relative_path)

                    indexed_count += 1
                    logger.info(f"  ✓ Indexed: {relative_path} ({len(chunks)} chunks)")

                except Exception as e:
                    logger.error(f"  ✗ Error indexing {md_file}: {e}")
                    error_count += 1

            await session.commit()

        # Close HTTP client (only for OpenRouter)
        if not self.use_openai:
            await self.client.aclose()

        logger.info(f"\n✅ Indexing complete!")
        logger.info(f"   Indexed: {indexed_count} files")
        logger.info(f"   Errors: {error_count}")

    async def _store_chunks(
        self,
        session: AsyncSession,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        file_path: str
    ):
        """
        Store chunks in appropriate database table.

        Args:
            session: Database session
            chunks: List of chunk dicts
            embeddings: List of embedding vectors
            file_path: File path for deletion
        """
        if self.doc_type == "shopify":
            await self._store_shopify_chunks(session, chunks, embeddings, file_path)
        else:
            await self._store_internal_chunks(session, chunks, embeddings, file_path)

    async def _store_shopify_chunks(
        self,
        session: AsyncSession,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        file_path: str
    ):
        """Store chunks in docs table (source of truth for full content)"""
        # Delete existing entry for this file
        await session.execute(
            text("DELETE FROM docs WHERE doc_path = :path"),
            {"path": file_path}
        )

        # For Shopify docs, we average embeddings and store one entry per file
        import numpy as np
        avg_embedding = np.mean(embeddings, axis=0).tolist()

        # Convert to halfvec string format: [1.0,2.0,3.0,...]
        halfvec_str = '[' + ','.join(str(v) for v in avg_embedding) + ']'

        # Parse metadata from path
        # file_path is already relative (e.g., "shopify-api/liquid/00-liquid-objects.md")
        relative_path = Path(file_path)
        parts = relative_path.parts

        api_version = parts[1] if len(parts) > 1 else None  # e.g., "admin"
        category = parts[2] if len(parts) > 2 else "general"

        # Extract title from first chunk
        title = chunks[0]['heading_context'].split(' / ')[0] if chunks[0]['heading_context'] else relative_path.stem

        # Combine all chunk text
        full_content = '\n\n'.join(chunk['chunk_text'] for chunk in chunks)

        # Insert into database with halfvec
        await session.execute(
            text("""
                INSERT INTO docs (doc_path, category, title, content, embedding_halfvec, api_version, metadata)
                VALUES (:doc_path, :category, :title, :content, CAST(:embedding AS halfvec), :api_version, :metadata)
            """),
            {
                "doc_path": file_path,
                "category": category,
                "title": title,
                "content": full_content,
                "embedding": halfvec_str,
                "api_version": api_version,
                "metadata": json.dumps({
                    "file_path": file_path,
                    "chunk_count": len(chunks),
                    "embedding_model": self.model_name,
                    "embedding_dim": len(avg_embedding),
                    "indexed_at": datetime.now(timezone.utc).isoformat()
                })
            }
        )

    async def _store_internal_chunks(
        self,
        session: AsyncSession,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        file_path: str
    ):
        """Store chunks in doc_chunks table using halfvec (derived data for search)"""
        # Delete existing chunks for this file
        await session.execute(
            text("DELETE FROM doc_chunks WHERE file_path = :path"),
            {"path": file_path}
        )

        # Insert new chunks with halfvec
        for chunk, embedding in zip(chunks, embeddings):
            # Convert to halfvec string format
            halfvec_str = '[' + ','.join(str(v) for v in embedding) + ']'

            await session.execute(
                text("""
                    INSERT INTO doc_chunks
                    (file_path, chunk_index, chunk_text, chunk_tokens, heading_context, embedding_halfvec, created_at, updated_at)
                    VALUES (:file_path, :chunk_index, :chunk_text, :chunk_tokens, :heading_context, CAST(:embedding AS halfvec), NOW(), NOW())
                """),
                {
                    "file_path": chunk['file_path'],
                    "chunk_index": chunk['chunk_index'],
                    "chunk_text": chunk['chunk_text'],
                    "chunk_tokens": chunk['chunk_tokens'],
                    "heading_context": chunk['heading_context'],
                    "embedding": halfvec_str
                }
            )


async def main():
    """CLI entry point for indexing"""
    import argparse

    parser = argparse.ArgumentParser(description="Index documentation with Qwen embeddings")
    parser.add_argument(
        "--type",
        choices=["internal", "shopify", "all"],
        default="all",
        help="Type of docs to index"
    )
    parser.add_argument("--force", action="store_true", help="Force re-index all documents")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Target chunk size in tokens"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Overlap between chunks in tokens"
    )

    args = parser.parse_args()

    if args.type in ["internal", "all"]:
        logger.info("\n" + "="*70)
        logger.info("  📚 Indexing Internal Documentation")
        logger.info("="*70)
        indexer = UnifiedDocsIndexer(
            doc_type="internal",
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap
        )
        await indexer.index_all(force=args.force)

    if args.type in ["shopify", "all"]:
        logger.info("\n" + "="*70)
        logger.info("  🛍️  Indexing Shopify Documentation")
        logger.info("="*70)
        indexer = UnifiedDocsIndexer(
            doc_type="shopify",
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap
        )
        await indexer.index_all(force=args.force)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
