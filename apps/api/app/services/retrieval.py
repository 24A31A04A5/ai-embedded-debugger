"""Document vector retrieval service using pgvector cosine similarity and domain-aware technical ranking."""

from __future__ import annotations

import logging
import math
import re
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


def extract_query_intent(query: str) -> dict[str, Any]:
    """Identify technical focus areas from query text (registers, pinouts, specifications)."""
    intent: dict[str, Any] = {}
    if not query:
        return intent

    q_lower = query.lower()

    if re.search(r"\b(?:register|bit|bits|offset|reset\s+value|0x[0-9a-f]+|cr\d+|sr\d+|dr\d+)\b", q_lower):
        intent["is_register"] = True
    if re.search(r"\b(?:pin|gpio\d*|pinout|sda|scl|rx|tx|mosi|miso|sck|pad|alternate\s+function)\b", q_lower):
        intent["is_pinout"] = True
    if re.search(r"\b(?:table|spec|specification|voltage|current|timing|max|min|typ|electrical|vcc|vdd|vss|frequency|baud)\b", q_lower):
        intent["is_spec"] = True

    return intent


class DocumentRetrievalService:
    """Vector similarity retrieval service over DocumentChunk embeddings scoped to a project with technical ranking."""

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
        section: str | None = None,
        content_type: str | None = None,
        page_number: int | None = None,
        has_register: bool | None = None,
        has_table: bool | None = None,
        has_pinout: bool | None = None,
        query_text: str | None = None,
    ) -> list[DocumentSearchResultItem]:
        """Search chunks in a project using a pre-computed embedding vector and optional metadata filters.

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

        if page_number is not None:
            query_stmt = query_stmt.filter(DocumentChunk.page_number == page_number)

        # Filter by similarity threshold
        if similarity_threshold > -1.0:
            query_stmt = query_stmt.filter(distance_expr <= (1.0 - similarity_threshold))

        # Retrieve candidates with oversampling for metadata filtering and technical re-ranking
        candidate_limit = max(top_k * 4, 25)
        query_stmt = query_stmt.order_by(distance_expr.asc()).limit(candidate_limit)

        rows = query_stmt.all()

        intent = extract_query_intent(query_text or "")
        scored_candidates: list[tuple[float, DocumentSearchResultItem]] = []

        for chunk, doc_name, score in rows:
            sim_score = float(score) if score is not None else 0.0
            meta = chunk.metadata_json or {}

            # Strict metadata filtering if requested
            if content_type and meta.get("content_type") != content_type:
                continue
            if has_register is not None and meta.get("has_register") != has_register:
                continue
            if has_table is not None and meta.get("has_table") != has_table:
                continue
            if has_pinout is not None and meta.get("has_pinout") != has_pinout:
                continue
            if section and section.lower() not in str(meta.get("section", "")).lower():
                continue

            # Technical intent ranking bonus
            rank_score = sim_score
            if intent.get("is_register") and (meta.get("has_register") or meta.get("content_type") == "register_description"):
                rank_score += 0.03
            if intent.get("is_pinout") and (meta.get("has_pinout") or meta.get("content_type") == "pin_configuration"):
                rank_score += 0.03
            if intent.get("is_spec") and (meta.get("has_table") or meta.get("content_type") == "table_or_specification"):
                rank_score += 0.03

            item = DocumentSearchResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=doc_name,
                content=chunk.content,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                similarity_score=sim_score,
                metadata_json=meta,
            )
            scored_candidates.append((rank_score, item))

        # Sort by technical rank score descending
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        return [item for _, item in scored_candidates[:top_k]]

    def search(
        self,
        project_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        document_ids: list[uuid.UUID] | None = None,
        section: str | None = None,
        content_type: str | None = None,
        page_number: int | None = None,
        has_register: bool | None = None,
        has_table: bool | None = None,
        has_pinout: bool | None = None,
    ) -> list[DocumentSearchResultItem]:
        """Generate query embedding and perform vector similarity search with domain-aware ranking.

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
            section=section,
            content_type=content_type,
            page_number=page_number,
            has_register=has_register,
            has_table=has_table,
            has_pinout=has_pinout,
            query_text=cleaned_query,
        )

