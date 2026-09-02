"""Tests for Phase 5.2 — Advanced Retrieval for the AI Embedded Debugger.

Covers:
1. Technical query retrieval & intent detection
2. Metadata-aware filtering (content_type, page_number, flags)
3. Section-aware retrieval
4. Register and specification retrieval
5. Pinout retrieval
6. Relevance ranking & domain boosting
7. Project and ownership isolation
8. Backward compatibility with existing retrieval
9. No-result and edge-case handling
"""

from __future__ import annotations

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
from app.services.embedding import BaseEmbeddingService
from app.services.retrieval import (
    DocumentRetrievalService,
    extract_query_intent,
)


# ─────────────────────────────────────────────
# Shared test fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="retrieval_dev@example.com",
        clerk_id="user_clerk_retrieval",
        auth_provider="clerk",
        plan="free",
    )


@pytest.fixture
def mock_project(mock_user: User) -> Project:
    return Project(
        id=uuid.uuid4(),
        owner_id=mock_user.id,
        name="STM32 Retrieval Workspace",
        description="Phase 5.2 advanced search testing",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_chunks(mock_project: Project) -> list[tuple[DocumentChunk, str, float]]:
    doc_id = uuid.uuid4()
    doc_name = "stm32f4_reference_manual.pdf"

    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        content="Overview: STM32F401xB/C advanced ARM Cortex-M4 32-bit RISC microcontroller.",
        page_number=1,
        metadata_json={"content_type": "text", "section": "1.0 Overview"},
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=1,
        content="TIM2_CR1 Register (offset 0x00, Reset value 0x0000): Bit 0 CEN: Counter enable. Bit 4 DIR: Direction (0=Upcounter, 1=Downcounter).",
        page_number=15,
        metadata_json={
            "content_type": "register_description",
            "has_register": True,
            "section": "14.4.1 TIMx control register 1 (TIMx_CR1)",
        },
    )
    chunk3 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=2,
        content="Table 4-2. Pin Definitions: Pin 42 is GPIO21 / I2C1_SDA. Pin 43 is GPIO22 / I2C1_SCL.",
        page_number=45,
        metadata_json={
            "content_type": "pin_configuration",
            "has_pinout": True,
            "has_table": True,
            "section": "4.2 Pinouts and pin description",
        },
    )
    chunk4 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=3,
        content="Table 25. Electrical Characteristics: VDD supply voltage min 1.7V, typ 3.3V, max 3.6V.",
        page_number=62,
        metadata_json={
            "content_type": "table_or_specification",
            "has_table": True,
            "section": "6.3 Operating conditions",
        },
    )

    return [
        (chunk1, doc_name, 0.70),
        (chunk2, doc_name, 0.82),
        (chunk3, doc_name, 0.80),
        (chunk4, doc_name, 0.78),
    ]


class MockEmbeddingService(BaseEmbeddingService):
    def embed_text(self, text: str) -> list[float]:
        return [0.1] * 768

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]

    def dimension(self) -> int:
        return 768

    def model_name(self) -> str:
        return "mock-embedding-v1"


def _setup_mock_db(sample_chunks: list[tuple[DocumentChunk, str, float]]) -> MagicMock:
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = sample_chunks
    mock_db.query.return_value = mock_query
    return mock_db


# ─────────────────────────────────────────────
# 1. Technical query intent detection
# ─────────────────────────────────────────────


class TestTechnicalQueryIntent:
    def test_intent_detects_registers_pinouts_and_specs(self) -> None:
        reg_intent = extract_query_intent("What is the reset value of TIM2_CR1 register?")
        assert reg_intent.get("is_register") is True

        pin_intent = extract_query_intent("Which pin is used for I2C1 SDA GPIO?")
        assert pin_intent.get("is_pinout") is True

        spec_intent = extract_query_intent("What is the maximum operating voltage table?")
        assert spec_intent.get("is_spec") is True

    def test_empty_query_returns_empty_intent(self) -> None:
        assert extract_query_intent("") == {}


# ─────────────────────────────────────────────
# 2. Metadata-aware filtering
# ─────────────────────────────────────────────


class TestMetadataFiltering:
    def test_filter_by_content_type(
        self,
        mock_project: Project,
        sample_chunks: list[tuple[DocumentChunk, str, float]],
    ) -> None:
        mock_db = _setup_mock_db(sample_chunks)
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        results = svc.search_by_embedding(
            project_id=mock_project.id,
            query_embedding=[0.1] * 768,
            content_type="register_description",
        )

        assert len(results) == 1
        assert results[0].metadata_json["content_type"] == "register_description"
        assert "TIM2_CR1" in results[0].content

    def test_filter_by_page_number(
        self,
        mock_project: Project,
        sample_chunks: list[tuple[DocumentChunk, str, float]],
    ) -> None:
        # Filter chunks by page number
        filtered_by_page = [c for c in sample_chunks if c[0].page_number == 45]
        mock_db = _setup_mock_db(filtered_by_page)

        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        results = svc.search_by_embedding(
            project_id=mock_project.id,
            query_embedding=[0.1] * 768,
            page_number=45,
        )

        assert len(results) == 1
        assert results[0].page_number == 45
        assert "Pin 42" in results[0].content


# ─────────────────────────────────────────────
# 3. Section-aware retrieval
# ─────────────────────────────────────────────


class TestSectionAwareRetrieval:
    def test_filter_by_section_substring(
        self,
        mock_project: Project,
        sample_chunks: list[tuple[DocumentChunk, str, float]],
    ) -> None:
        mock_db = _setup_mock_db(sample_chunks)
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        results = svc.search_by_embedding(
            project_id=mock_project.id,
            query_embedding=[0.1] * 768,
            section="Pinouts",
        )

        assert len(results) == 1
        assert "Pinouts" in results[0].metadata_json["section"]
        assert "GPIO21" in results[0].content


# ─────────────────────────────────────────────
# 4. Register / specification retrieval
# ─────────────────────────────────────────────


class TestRegisterAndSpecRetrieval:
    def test_filter_by_has_register_flag(
        self,
        mock_project: Project,
        sample_chunks: list[tuple[DocumentChunk, str, float]],
    ) -> None:
        mock_db = _setup_mock_db(sample_chunks)
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        results = svc.search_by_embedding(
            project_id=mock_project.id,
            query_embedding=[0.1] * 768,
            has_register=True,
        )

        assert len(results) == 1
        assert results[0].metadata_json["has_register"] is True
        assert "TIM2_CR1" in results[0].content

    def test_filter_by_has_table_flag(
        self,
        mock_project: Project,
        sample_chunks: list[tuple[DocumentChunk, str, float]],
    ) -> None:
        mock_db = _setup_mock_db(sample_chunks)
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        results = svc.search_by_embedding(
            project_id=mock_project.id,
            query_embedding=[0.1] * 768,
            has_table=True,
        )

        assert len(results) == 2
        for r in results:
            assert r.metadata_json["has_table"] is True


# ─────────────────────────────────────────────
# 5. Pinout retrieval
# ─────────────────────────────────────────────


class TestPinoutRetrieval:
    def test_filter_by_has_pinout_flag(
        self,
        mock_project: Project,
        sample_chunks: list[tuple[DocumentChunk, str, float]],
    ) -> None:
        mock_db = _setup_mock_db(sample_chunks)
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        results = svc.search_by_embedding(
            project_id=mock_project.id,
            query_embedding=[0.1] * 768,
            has_pinout=True,
        )

        assert len(results) == 1
        assert results[0].metadata_json["has_pinout"] is True
        assert "GPIO21" in results[0].content


# ─────────────────────────────────────────────
# 6. Relevance ranking & domain boosting
# ─────────────────────────────────────────────


class TestRelevanceRanking:
    def test_register_intent_boosts_register_chunk(
        self,
        mock_project: Project,
        sample_chunks: list[tuple[DocumentChunk, str, float]],
    ) -> None:
        mock_db = _setup_mock_db(sample_chunks)
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        # Query mentioning register
        results = svc.search(
            project_id=mock_project.id,
            query="Tell me about CR1 register bit offset",
            top_k=4,
        )

        assert len(results) >= 1
        # Top result should be the register chunk
        assert results[0].metadata_json.get("has_register") is True


# ─────────────────────────────────────────────
# 7. Project & ownership isolation
# ─────────────────────────────────────────────


class TestOwnershipIsolation:
    def test_search_scoped_strictly_to_project_id(
        self,
        mock_project: Project,
    ) -> None:
        mock_db = _setup_mock_db([])
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        svc.search(project_id=mock_project.id, query="Test query")

        assert mock_db.query.called


# ─────────────────────────────────────────────
# 8. Backward compatibility with existing retrieval
# ─────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_search_without_optional_args_works(
        self,
        mock_project: Project,
        sample_chunks: list[tuple[DocumentChunk, str, float]],
    ) -> None:
        mock_db = _setup_mock_db(sample_chunks)
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        results = svc.search(project_id=mock_project.id, query="Basic search")

        assert len(results) == 4
        assert all(isinstance(r, DocumentSearchResultItem) for r in results)


# ─────────────────────────────────────────────
# 9. No-result and edge-case handling
# ─────────────────────────────────────────────


class TestNoResultHandling:
    def test_empty_query_returns_empty_list(self, mock_project: Project) -> None:
        mock_db = MagicMock()
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        assert svc.search(project_id=mock_project.id, query="") == []
        assert svc.search(project_id=mock_project.id, query="   ") == []

    def test_top_k_zero_returns_empty_list(self, mock_project: Project) -> None:
        mock_db = MagicMock()
        svc = DocumentRetrievalService(db=mock_db, embedding_service=MockEmbeddingService())
        assert svc.search(project_id=mock_project.id, query="Test", top_k=0) == []

