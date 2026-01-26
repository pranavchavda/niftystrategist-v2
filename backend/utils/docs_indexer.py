"""
Documentation indexer for semantic search.

Chunks documentation files and generates embeddings for RAG retrieval.
"""

import os
import re
import json
import logging
import tiktoken
from typing import List, Tuple, Optional
from pathlib import Path
from datetime import datetime, timezone
from utils.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a chunk of documentation"""
    def __init__(
        self,
        file_path: str,
        chunk_index: int,
        chunk_text: str,
        heading_context: str = "",
        chunk_tokens: int = 0
    ):
        self.file_path = file_path
        self.chunk_index = chunk_index
        self.chunk_text = chunk_text
        self.heading_context = heading_context
        self.chunk_tokens = chunk_tokens


class DocsIndexer:
    """Index documentation files with embeddings for semantic search"""

    def __init__(self, docs_dir: str, chunk_size: int = 800, chunk_overlap: int = 100):
        """
        Initialize docs indexer.

        Args:
            docs_dir: Path to documentation directory
            chunk_size: Target chunk size in tokens (default 800)
            chunk_overlap: Overlap between chunks in tokens (default 100)
        """
        self.docs_dir = Path(docs_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.encoding_for_model("gpt-4")  # Same tokenizer as OpenAI

    def scan_docs_directory(self) -> List[Path]:
        """
        Scan docs directory for markdown files.

        Returns:
            List of Path objects for .md files
        """
        md_files = []
        for root, dirs, files in os.walk(self.docs_dir):
            for file in files:
                if file.endswith('.md'):
                    file_path = Path(root) / file
                    md_files.append(file_path)

        logger.info(f"Found {len(md_files)} markdown files in {self.docs_dir}")
        return md_files

    def chunk_markdown(self, content: str, file_path: str) -> List[DocumentChunk]:
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
            List of DocumentChunk objects
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
                    chunks.append(DocumentChunk(
                        file_path=file_path,
                        chunk_index=chunk_index,
                        chunk_text=sub_chunk_text,
                        heading_context=heading,
                        chunk_tokens=sub_tokens
                    ))
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
                chunks.append(DocumentChunk(
                    file_path=file_path,
                    chunk_index=chunk_index,
                    chunk_text=chunk_text,
                    heading_context=combined_heading,
                    chunk_tokens=combined_tokens
                ))
                chunk_index += 1
                i = j  # Continue from next uncombined section

        logger.info(f"Created {len(chunks)} chunks from {file_path}")
        return chunks

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

    def _split_by_paragraphs(self, text: str, heading: str) -> List[Tuple[str, int]]:
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

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        return len(self.encoding.encode(text))

    async def generate_embeddings(self, chunks: List[DocumentChunk]) -> List[List[float]]:
        """
        Generate embeddings for chunks using OpenAI API.

        Args:
            chunks: List of DocumentChunk objects

        Returns:
            List of embedding vectors (3072-dim)
        """
        import openai
        import os

        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        texts = [chunk.chunk_text for chunk in chunks]
        embeddings = []

        # Batch requests (max 2048 texts per request)
        batch_size = 100  # Conservative batch size
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                response = await client.embeddings.create(
                    model="text-embedding-3-large",
                    input=batch
                )

                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)

                logger.info(f"Generated embeddings for {len(batch)} chunks (batch {i//batch_size + 1})")

            except Exception as e:
                logger.error(f"Failed to generate embeddings for batch {i//batch_size + 1}: {e}")
                # Add None for failed chunks
                embeddings.extend([None] * len(batch))

        return embeddings

    async def upsert_to_database(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[Optional[List[float]]],
        session
    ) -> int:
        """
        Insert or update chunks in database.

        Args:
            chunks: List of DocumentChunk objects
            embeddings: List of embedding vectors (or None)
            session: Database session

        Returns:
            Number of chunks upserted
        """
        from database.models import DocumentationChunk
        from sqlalchemy import delete

        if len(chunks) != len(embeddings):
            raise ValueError(f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch")

        # Delete existing chunks for this file (simplest approach for updates)
        file_paths = set(chunk.file_path for chunk in chunks)
        for file_path in file_paths:
            await session.execute(
                delete(DocumentationChunk).where(DocumentationChunk.file_path == file_path)
            )
            logger.info(f"Deleted existing chunks for {file_path}")

        # Insert new chunks
        upserted = 0
        for chunk, embedding in zip(chunks, embeddings):
            db_chunk = DocumentationChunk(
                file_path=chunk.file_path,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                chunk_tokens=chunk.chunk_tokens,
                heading_context=chunk.heading_context,
                embedding=embedding,  # Store as JSON array
                created_at=utc_now_naive(),
                updated_at=utc_now_naive()
            )
            session.add(db_chunk)
            upserted += 1

        await session.commit()
        logger.info(f"Upserted {upserted} chunks to database")
        return upserted

    async def reindex_all(self, session) -> dict:
        """
        Reindex all documentation files.

        Args:
            session: Database session

        Returns:
            Dict with stats: {files: int, chunks: int, tokens: int}
        """
        logger.info("Starting full documentation reindex...")

        all_chunks = []
        total_tokens = 0

        # Scan and chunk all files
        md_files = self.scan_docs_directory()

        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Get relative path
                rel_path = str(md_file.relative_to(self.docs_dir.parent))

                # Chunk the file
                file_chunks = self.chunk_markdown(content, rel_path)
                all_chunks.extend(file_chunks)
                total_tokens += sum(chunk.chunk_tokens for chunk in file_chunks)

            except Exception as e:
                logger.error(f"Failed to process {md_file}: {e}")
                continue

        logger.info(f"Chunked {len(md_files)} files into {len(all_chunks)} chunks ({total_tokens} tokens)")

        # Generate embeddings
        embeddings = await self.generate_embeddings(all_chunks)

        # Upsert to database
        await self.upsert_to_database(all_chunks, embeddings, session)

        return {
            'files': len(md_files),
            'chunks': len(all_chunks),
            'tokens': total_tokens
        }

    async def reindex_file(self, file_path: str, session) -> dict:
        """
        Reindex a single file.

        Args:
            file_path: Relative path to file (e.g., "docs/product-guidelines/breville.md")
            session: Database session

        Returns:
            Dict with stats: {chunks: int, tokens: int}
        """
        logger.info(f"Reindexing file: {file_path}")

        abs_path = self.docs_dir.parent / file_path

        if not abs_path.exists():
            raise FileNotFoundError(f"File not found: {abs_path}")

        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Chunk the file
        chunks = self.chunk_markdown(content, file_path)
        total_tokens = sum(chunk.chunk_tokens for chunk in chunks)

        logger.info(f"Created {len(chunks)} chunks ({total_tokens} tokens)")

        # Generate embeddings
        embeddings = await self.generate_embeddings(chunks)

        # Upsert to database
        await self.upsert_to_database(chunks, embeddings, session)

        return {
            'chunks': len(chunks),
            'tokens': total_tokens
        }
