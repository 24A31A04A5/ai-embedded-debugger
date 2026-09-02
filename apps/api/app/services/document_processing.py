"""Document processing pipeline — orchestrates chunking and embedding for an extracted document."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import RawChunk
from app.services.chunking import DocumentChunkingService
from app.services.embedding import BaseEmbeddingService, EmbeddingError, get_embedding_service

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Orchestrate chunking and embedding generation for a document.

    Usage:
        svc = DocumentProcessingService(db)
        svc.process_document(document, extracted_text, page_texts)
    """

    def __init__(
        self,
        db: Session,
        embedding_service: BaseEmbeddingService | None = None,
        chunking_service: DocumentChunkingService | None = None,
    ) -> None:
        self.db = db
        settings = get_settings()
        self.chunking = chunking_service or DocumentChunkingService(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        self._embedding_service = embedding_service

    @property
    def embedding_service(self) -> BaseEmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    def process_document(
        self,
        document: Document,
        extracted_text: str,
        page_texts: list[str] | None = None,
    ) -> list[DocumentChunk]:
        """Chunk text, generate embeddings, persist DocumentChunk rows.

        Returns the list of persisted chunks.
        Raises on failure — caller is responsible for updating document status.
        """
        # 1. Chunk
        raw_chunks: list[RawChunk] = self.chunking.chunk_text(extracted_text, page_texts)
        if not raw_chunks:
            logger.info("Document %s produced 0 chunks (empty text).", document.id)
            return []

        # 2. Generate embeddings for all chunks in one batch
        texts = [c.content for c in raw_chunks]
        embeddings: list[list[float]] = []
        model_name: str = ""
        try:
            svc = self.embedding_service
            model_name = svc.model_name()
            embeddings = svc.embed_batch(texts)
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(f"Embedding pipeline failure: {e}") from e

        if len(embeddings) != len(raw_chunks):
            raise EmbeddingError(
                f"Embedding count mismatch: {len(embeddings)} vs {len(raw_chunks)} chunks"
            )

        # 3. Persist
        now = datetime.now(UTC)
        db_chunks: list[DocumentChunk] = []
        for raw, emb in zip(raw_chunks, embeddings):
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=raw.chunk_index,
                content=raw.content,
                page_number=raw.page_number,
                metadata_json=raw.metadata or {},
                embedding_model=model_name,
                embedding=emb,
                created_at=now,
            )
            self.db.add(chunk)
            db_chunks.append(chunk)

        self.db.flush()  # Assign IDs, let caller commit
        logger.info(
            "Processed document %s: %d chunks, model=%s",
            document.id,
            len(db_chunks),
            model_name,
        )
        return db_chunks
