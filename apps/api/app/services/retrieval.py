"""Document vector retrieval service using pgvector cosine similarity."""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentSearchResultItem
from app.services.embedding import BaseEmbeddingService, EmbeddingError, get_embedding_service

logger = logging.getLogger(__name__)


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculate cosine similarity between two float vectors.

    similarity = (A . B) / (||A|| * ||B||)
    Returns a float in the range [-1.0, 1.0], or 0.0 if either vector has zero magnitude.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class DocumentRetrievalService:
    """Vector similarity retrieval service over DocumentChunk embeddings scoped to a project."""

    def __init__(
        self,
        db: Session,
        embedding_service: BaseEmbeddingService | None = None,
    ) -> None:
        self.db = db
        self._embedding_service = embedding_service

    @property
    def embedding_service(self) -> BaseEmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    def search_by_embedding(
        self,
        project_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[DocumentSearchResultItem]:
        """Search chunks in a project using a pre-computed embedding vector.

        Scoped strictly to documents belonging to `project_id`.
        """
        if top_k <= 0:
            return []

        # Cosine distance operator in pgvector: <=>
        # cosine_similarity = 1.0 - cosine_distance
        distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)
        similarity_expr = (1.0 - distance_expr).label("similarity_score")

        query_stmt = (
            self.db.query(
                DocumentChunk,
                Document.filename.label("document_name"),
                similarity_expr,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(Document.project_id == project_id)
            .filter(DocumentChunk.embedding.isnot(None))
        )

        if document_ids:
            query_stmt = query_stmt.filter(Document.id.in_(document_ids))

        # Filter by similarity threshold: similarity >= threshold <=> distance <= (1 - threshold)
        if similarity_threshold > -1.0:
            query_stmt = query_stmt.filter(distance_expr <= (1.0 - similarity_threshold))

        query_stmt = query_stmt.order_by(distance_expr.asc()).limit(top_k)

        rows = query_stmt.all()

        results: list[DocumentSearchResultItem] = []
        for chunk, doc_name, score in rows:
            # Score may be None or Decimal/float depending on driver/mock
            sim_score = float(score) if score is not None else 0.0
            results.append(
                DocumentSearchResultItem(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=doc_name,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    similarity_score=sim_score,
                    metadata_json=chunk.metadata_json,
                )
            )

        return results

    def search(
        self,
        project_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[DocumentSearchResultItem]:
        """Generate query embedding and perform vector similarity search within project scope.

        Returns ranked list of matching chunks with metadata and similarity scores.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        try:
            svc = self.embedding_service
            query_embedding = svc.embed_text(cleaned_query)
        except EmbeddingError:
            raise
        except Exception as e:
            logger.error("Failed to generate query embedding: %s", e)
            raise EmbeddingError(f"Failed to generate query embedding: {e}") from e

        return self.search_by_embedding(
            project_id=project_id,
            query_embedding=query_embedding,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            document_ids=document_ids,
        )
