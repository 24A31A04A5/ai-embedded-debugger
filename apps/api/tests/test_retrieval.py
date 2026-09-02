"""Tests for Phase 3.3 — Vector Search & Retrieval."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.project import Project
from app.models.user import User
from app.schemas.document import DocumentSearchRequest, DocumentSearchResultItem
from app.services.embedding import BaseEmbeddingService, EmbeddingError
from app.services.retrieval import DocumentRetrievalService, compute_cosine_similarity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="dev@example.com",
        clerk_id="user_clerk_retrieval",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def other_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="other@example.com",
        clerk_id="user_other_retrieval",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="ESP32 Vector Search Project",
        description="Datasheet Search Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def other_project(other_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=other_user.id,
        name="STM32 Isolated Project",
        description="Other Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def make_test_chunk(
    doc_id: uuid.UUID,
    chunk_index: int = 0,
    content: str = "Test chunk content",
    page_number: int | None = 1,
    metadata_json: dict | None = None,
    embedding: list[float] | None = None,
) -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=chunk_index,
        content=content,
        page_number=page_number,
        metadata_json=metadata_json or {"heading": "Section 1"},
        embedding_model="gemini-embedding-001",
        embedding=embedding or [0.1] * 3072,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Cosine similarity math tests
# ---------------------------------------------------------------------------


class TestCosineSimilarityMath:
    """Unit tests for compute_cosine_similarity pure function."""

    def test_identical_vectors_return_one(self) -> None:
        v1 = [1.0, 2.0, 3.0]
        assert pytest.approx(compute_cosine_similarity(v1, v1), rel=1e-5) == 1.0

    def test_orthogonal_vectors_return_zero(self) -> None:
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert pytest.approx(compute_cosine_similarity(v1, v2), rel=1e-5) == 0.0

    def test_opposite_vectors_return_minus_one(self) -> None:
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert pytest.approx(compute_cosine_similarity(v1, v2), rel=1e-5) == -1.0

    def test_arbitrary_vectors_calculation(self) -> None:
        v1 = [1.0, 2.0, 3.0]
        v2 = [4.0, 5.0, 6.0]
        # dot = 4 + 10 + 18 = 32
        # ||v1|| = sqrt(1+4+9) = sqrt(14)
        # ||v2|| = sqrt(16+25+36) = sqrt(77)
        expected = 32.0 / (math.sqrt(14) * math.sqrt(77))
        assert pytest.approx(compute_cosine_similarity(v1, v2), rel=1e-5) == expected

    def test_empty_or_mismatched_vectors_return_zero(self) -> None:
        assert compute_cosine_similarity([], []) == 0.0
        assert compute_cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vector_returns_zero(self) -> None:
        assert compute_cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


# ---------------------------------------------------------------------------
# DocumentRetrievalService unit tests
# ---------------------------------------------------------------------------


class TestDocumentRetrievalService:
    """Unit tests for DocumentRetrievalService."""

    def test_empty_or_whitespace_query_returns_empty_list(self) -> None:
        mock_db = MagicMock()
        mock_emb = MagicMock(spec=BaseEmbeddingService)
        svc = DocumentRetrievalService(db=mock_db, embedding_service=mock_emb)

        assert svc.search(uuid.uuid4(), "") == []
        assert svc.search(uuid.uuid4(), "   ") == []
        assert not mock_emb.embed_text.called
        assert not mock_db.query.called

    def test_top_k_zero_or_negative_returns_empty_list(self) -> None:
        mock_db = MagicMock()
        mock_emb = MagicMock(spec=BaseEmbeddingService)
        mock_emb.embed_text.return_value = [0.1] * 3072
        svc = DocumentRetrievalService(db=mock_db, embedding_service=mock_emb)

        assert svc.search(uuid.uuid4(), "query", top_k=0) == []
        assert svc.search(uuid.uuid4(), "query", top_k=-1) == []
        assert not mock_db.query.called

    def test_search_retrieves_and_maps_chunks_with_metadata(self) -> None:
        mock_db = MagicMock()
        mock_emb = MagicMock(spec=BaseEmbeddingService)
        mock_emb.embed_text.return_value = [0.1] * 3072

        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        chunk = DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            chunk_index=2,
            content="ESP32 pin 4 is GPIO4 with capacitive touch support.",
            page_number=7,
            metadata_json={"section": "Pin Definitions"},
            embedding_model="gemini-embedding-001",
            embedding=[0.1] * 3072,
            created_at=datetime.now(UTC),
        )

        # Mock db.query(...).join(...).filter(...).filter(...).order_by(...).limit(...).all()
        mock_query = mock_db.query.return_value
        mock_join = mock_query.join.return_value
        mock_filter1 = mock_join.filter.return_value
        mock_filter2 = mock_filter1.filter.return_value
        mock_filter3 = mock_filter2.filter.return_value
        mock_order = mock_filter3.order_by.return_value
        # When similarity_threshold > -1.0, there are filter calls
        mock_order.limit.return_value.all.return_value = [
            (chunk, "esp32_datasheet.pdf", 0.92)
        ]
        # Fallback chain for flexible filter mocking
        mock_filter2.order_by.return_value.limit.return_value.all.return_value = [
            (chunk, "esp32_datasheet.pdf", 0.92)
        ]

        svc = DocumentRetrievalService(db=mock_db, embedding_service=mock_emb)
        proj_id = uuid.uuid4()
        results = svc.search(
            project_id=proj_id,
            query="ESP32 capacitive touch pin",
            top_k=5,
            similarity_threshold=0.5,
        )

        assert len(results) == 1
        item = results[0]
        assert isinstance(item, DocumentSearchResultItem)
        assert item.chunk_id == chunk_id
        assert item.document_id == doc_id
        assert item.document_name == "esp32_datasheet.pdf"
        assert item.content == "ESP32 pin 4 is GPIO4 with capacitive touch support."
        assert item.page_number == 7
        assert item.chunk_index == 2
        assert item.similarity_score == 0.92
        assert item.metadata_json == {"section": "Pin Definitions"}
        mock_emb.embed_text.assert_called_once_with("ESP32 capacitive touch pin")

    def test_embedding_service_failure_propagates_embedding_error(self) -> None:
        mock_db = MagicMock()
        mock_emb = MagicMock(spec=BaseEmbeddingService)
        mock_emb.embed_text.side_effect = EmbeddingError("API quota exceeded")

        svc = DocumentRetrievalService(db=mock_db, embedding_service=mock_emb)
        with pytest.raises(EmbeddingError, match="API quota exceeded"):
            svc.search(uuid.uuid4(), "query text")

    def test_search_by_embedding_with_document_ids_filter(self) -> None:
        mock_db = MagicMock()
        mock_query = mock_db.query.return_value
        mock_join = mock_query.join.return_value
        mock_f1 = mock_join.filter.return_value
        mock_f2 = mock_f1.filter.return_value
        mock_f3 = mock_f2.filter.return_value
        mock_f4 = mock_f3.filter.return_value
        mock_order = mock_f4.order_by.return_value
        mock_order.limit.return_value.all.return_value = []
        mock_f3.order_by.return_value.limit.return_value.all.return_value = []
        mock_f2.order_by.return_value.limit.return_value.all.return_value = []

        svc = DocumentRetrievalService(db=mock_db)
        doc_a = uuid.uuid4()
        doc_b = uuid.uuid4()
        results = svc.search_by_embedding(
            project_id=uuid.uuid4(),
            query_embedding=[0.1] * 3072,
            top_k=3,
            similarity_threshold=0.0,
            document_ids=[doc_a, doc_b],
        )

        assert results == []
        assert mock_db.query.called


# ---------------------------------------------------------------------------
# API Endpoint tests: POST /v1/projects/{project_id}/documents/search
# ---------------------------------------------------------------------------


class TestDocumentSearchEndpoint:
    """Integration and router tests for the document search endpoint."""

    def test_search_documents_success(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        # Mock get_project_for_user lookup
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        mock_retrieval = MagicMock(spec=DocumentRetrievalService)
        chunk_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        mock_result = DocumentSearchResultItem(
            chunk_id=chunk_id,
            document_id=doc_id,
            document_name="stm32f4_manual.pdf",
            content="TIM2 is a 32-bit general-purpose timer.",
            page_number=142,
            chunk_index=3,
            similarity_score=0.88,
            metadata_json={"chapter": "Timers"},
        )
        mock_retrieval.search.return_value = [mock_result]

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        from app.routers.documents import get_retrieval_service
        app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/documents/search",
                json={
                    "query": "How many bits is TIM2?",
                    "top_k": 3,
                    "similarity_threshold": 0.5,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "How many bits is TIM2?"
            assert data["total_results"] == 1
            assert len(data["results"]) == 1
            res_item = data["results"][0]
            assert res_item["chunk_id"] == str(chunk_id)
            assert res_item["document_id"] == str(doc_id)
            assert res_item["document_name"] == "stm32f4_manual.pdf"
            assert res_item["content"] == "TIM2 is a 32-bit general-purpose timer."
            assert res_item["page_number"] == 142
            assert res_item["chunk_index"] == 3
            assert res_item["similarity_score"] == 0.88
            assert res_item["metadata_json"] == {"chapter": "Timers"}

            mock_retrieval.search.assert_called_once_with(
                project_id=mock_project.id,
                query="How many bits is TIM2?",
                top_k=3,
                similarity_threshold=0.5,
                document_ids=None,
            )
        finally:
            app.dependency_overrides.clear()

    def test_search_documents_with_document_ids_filter(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        mock_retrieval = MagicMock(spec=DocumentRetrievalService)
        mock_retrieval.search.return_value = []

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        from app.routers.documents import get_retrieval_service
        app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval

        doc_filter_id = uuid.uuid4()

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/documents/search",
                json={
                    "query": "I2C clock speed",
                    "top_k": 5,
                    "document_ids": [str(doc_filter_id)],
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_results"] == 0
            assert data["results"] == []

            mock_retrieval.search.assert_called_once_with(
                project_id=mock_project.id,
                query="I2C clock speed",
                top_k=5,
                similarity_threshold=0.0,
                document_ids=[doc_filter_id],
            )
        finally:
            app.dependency_overrides.clear()

    def test_search_unauthorized_or_other_user_project_returns_404(
        self,
        mock_user: User,
        other_project: Project,
    ) -> None:
        """Searching a project owned by another user must return 404 (not found / unauthorized)."""
        mock_db = MagicMock()
        # Query for project returns None (ownership filter failed)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{other_project.id}/documents/search",
                json={"query": "secret project documents"},
            )
            assert response.status_code == 404
            assert "Project not found" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_search_invalid_project_id_returns_404(
        self,
        mock_user: User,
    ) -> None:
        mock_db = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.post(
                "/v1/projects/not-a-valid-uuid/documents/search",
                json={"query": "query"},
            )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_search_empty_query_string_fails_validation(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/documents/search",
                json={"query": ""},
            )
            # Pydantic min_length=1 raises 422 Unprocessable Entity
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_search_embedding_failure_returns_502(
        self,
        mock_user: User,
        mock_project: Project,
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        mock_retrieval = MagicMock(spec=DocumentRetrievalService)
        mock_retrieval.search.side_effect = EmbeddingError("Gemini API down")

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        from app.routers.documents import get_retrieval_service
        app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval

        client = TestClient(app)
        try:
            response = client.post(
                f"/v1/projects/{mock_project.id}/documents/search",
                json={"query": "test query"},
            )
            assert response.status_code == 502
            assert "Embedding service failure" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()
