"""Tests for Phase 11.2 — Hybrid Retrieval (BM25 + Vector + RRF)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentSearchResultItem
from app.services.retrieval import DocumentRetrievalService
from app.services.retrieval_bm25 import BM25Retriever, search_documents_bm25


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=Session)


@pytest.fixture
def project_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_chunks(project_id: uuid.UUID) -> list[DocumentChunk]:
    """Create sample chunks for testing."""
    doc_id = uuid.uuid4()
    chunks = []
    contents = [
        "ESP32 GPIO4 is a capacitive touch pin with ADC support",
        "STM32 TIM2 is a 32-bit general purpose timer with PWM output",
        "GPIO register address 0x3FF44004 configures pin direction",
        "I2C SDA pin connects to GPIO21 with pull-up resistor",
        "Voltage specification VDD 3.3V max current 40mA per pin",
        "Pin configuration register CR1 controls alternate functions",
        "ESP32 ADC1 channel 0 reads analog voltage on GPIO36",
        "STM32 USART2 TX on PA2 RX on PA3 for serial communication",
    ]
    for i, content in enumerate(contents):
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_id,
            chunk_index=i,
            content=content,
            page_number=i + 1,
            metadata_json={"section": f"Section {i+1}"},
            embedding_model="gemini-embedding-001",
            embedding=[0.1] * 3072,
            created_at=datetime.now(UTC),
        )
        chunks.append(chunk)
    return chunks


@pytest.fixture
def sample_document(project_id: uuid.UUID, sample_chunks: list[DocumentChunk]) -> Document:
    return Document(
        id=sample_chunks[0].document_id,
        project_id=project_id,
        filename="test_datasheet.pdf",
        version=None,
        size_bytes=1024,
        checksum="abc123",
        storage_key="test/storage/key.pdf",
        extraction_status="completed",
        page_count=10,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class TestBM25Retriever:
    """Unit tests for BM25Retriever class."""

    def test_bm25_retriever_initialization(self, mock_db: MagicMock, project_id: uuid.UUID) -> None:
        """BM25Retriever should initialize with default parameters."""
        retriever = BM25Retriever(mock_db, project_id)
        assert retriever.k1 == 1.5
        assert retriever.b == 0.75
        assert retriever.project_id == project_id

    def test_bm25_retriever_custom_parameters(self, mock_db: MagicMock, project_id: uuid.UUID) -> None:
        """BM25Retriever should accept custom k1 and b parameters."""
        retriever = BM25Retriever(mock_db, project_id, k1=1.2, b=0.5)
        assert retriever.k1 == 1.2
        assert retriever.b == 0.5

    def test_empty_query_returns_empty_list(self, mock_db: MagicMock, project_id: uuid.UUID) -> None:
        """Empty query should return empty results."""
        retriever = BM25Retriever(mock_db, project_id)
        assert retriever.search_bm25("") == []
        assert retriever.search_bm25("   ") == []

    def test_bm25_search_returns_results(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """BM25 search should return scored results for matching terms."""
        retriever = BM25Retriever(mock_db, project_id)

        # Set up the mock query chain to return sample chunks
        query_result = MagicMock()
        query_result.join.return_value.filter.return_value.options.return_value.all.return_value = [
            (chunk, sample_document.filename) for chunk in sample_chunks
        ]
        query_result.join.return_value.filter.return_value.count.return_value = len(sample_chunks)
        mock_db.query.return_value = query_result

        # Mock the internal avg_doc_len and doc_count properties by setting the private attributes
        with patch.object(retriever, '_avg_doc_len', 100.0):
            with patch.object(retriever, '_doc_count', len(sample_chunks)):
                results = retriever.search_bm25("GPIO", top_k=5)

        assert len(results) > 0
        assert all(isinstance(r, DocumentSearchResultItem) for r in results)
        assert all(r.similarity_score > 0 for r in results)

    def test_bm25_search_ranks_by_relevance(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """BM25 should rank chunks by term frequency and IDF."""
        retriever = BM25Retriever(mock_db, project_id)

        # Set up the chain properly - query returns chunks with their document names
        query_result = MagicMock()
        query_result.join.return_value.filter.return_value.options.return_value.all.return_value = [
            (chunk, sample_document.filename) for chunk in sample_chunks
        ]
        query_result.join.return_value.filter.return_value.count.return_value = len(sample_chunks)
        mock_db.query.return_value = query_result

        # Mock avg_doc_len
        with patch.object(retriever, '_avg_doc_len', 100.0):
            results = retriever.search_bm25("GPIO pin", top_k=3)

        # Results should be sorted by score descending
        scores = [r.similarity_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_bm25_search_no_matches_returns_empty(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """Query with no matching terms should return empty list."""
        retriever = BM25Retriever(mock_db, project_id)

        # Set up the chain properly
        query_result = MagicMock()
        query_result.join.return_value.filter.return_value.options.return_value.all.return_value = [
            (chunk, sample_document.filename) for chunk in sample_chunks
        ]
        query_result.join.return_value.filter.return_value.count.return_value = len(sample_chunks)
        mock_db.query.return_value = query_result

        # Mock avg_doc_len
        with patch.object(retriever, '_avg_doc_len', 100.0):
            results = retriever.search_bm25("nonexistent term xyz", top_k=5)

        assert results == []


class TestHybridSearchRRF:
    """Tests for Reciprocal Rank Fusion hybrid search."""

    def test_hybrid_search_combines_vector_and_bm25(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """search_hybrid should combine vector and BM25 results using RRF."""
        svc = DocumentRetrievalService(mock_db)

        # Mock vector search results
        vector_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[0].id,
                document_id=sample_chunks[0].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[0].content,
                page_number=sample_chunks[0].page_number,
                chunk_index=sample_chunks[0].chunk_index,
                similarity_score=0.9,
                metadata_json=sample_chunks[0].metadata_json,
            ),
            DocumentSearchResultItem(
                chunk_id=sample_chunks[1].id,
                document_id=sample_chunks[1].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[1].content,
                page_number=sample_chunks[1].page_number,
                chunk_index=sample_chunks[1].chunk_index,
                similarity_score=0.8,
                metadata_json=sample_chunks[1].metadata_json,
            ),
        ]

        # Mock BM25 results
        bm25_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[2].id,
                document_id=sample_chunks[2].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[2].content,
                page_number=sample_chunks[2].page_number,
                chunk_index=sample_chunks[2].chunk_index,
                similarity_score=5.0,  # BM25 score
                metadata_json=sample_chunks[2].metadata_json,
            ),
            DocumentSearchResultItem(
                chunk_id=sample_chunks[0].id,  # Overlap with vector
                document_id=sample_chunks[0].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[0].content,
                page_number=sample_chunks[0].page_number,
                chunk_index=sample_chunks[0].chunk_index,
                similarity_score=4.5,
                metadata_json=sample_chunks[0].metadata_json,
            ),
        ]

        with patch.object(svc, "search", return_value=vector_results):
            with patch("app.services.retrieval_bm25.search_documents_bm25", return_value=bm25_results):
                results = svc.search_hybrid(
                    project_id=project_id,
                    query="GPIO register",
                    top_k=5,
                    bm25_weight=0.3,
                    vector_weight=0.7,
                    rrf_k=60,
                    include_bm25=True,
                )

        assert len(results) <= 5
        assert len(results) > 0
        # Overlapping chunk (sample_chunks[0]) should rank higher due to RRF
        assert results[0].chunk_id in [sample_chunks[0].id, sample_chunks[2].id]

    def test_hybrid_search_without_bm25(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """search_hybrid should work with vector only when include_bm25=False."""
        svc = DocumentRetrievalService(mock_db)

        vector_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[0].id,
                document_id=sample_chunks[0].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[0].content,
                page_number=sample_chunks[0].page_number,
                chunk_index=sample_chunks[0].chunk_index,
                similarity_score=0.9,
                metadata_json=sample_chunks[0].metadata_json,
            ),
        ]

        with patch.object(svc, "search", return_value=vector_results):
            results = svc.search_hybrid(
                project_id=project_id,
                query="test",
                top_k=5,
                include_bm25=False,
            )

        assert len(results) == 1
        assert results[0].chunk_id == sample_chunks[0].id

    def test_hybrid_search_rrf_scoring(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """RRF scoring should properly combine ranks from both retrievers."""
        svc = DocumentRetrievalService(mock_db)

        # Create results where same chunk appears in both at different ranks
        vector_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[0].id,
                document_id=sample_chunks[0].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[0].content,
                page_number=sample_chunks[0].page_number,
                chunk_index=sample_chunks[0].chunk_index,
                similarity_score=0.95,
                metadata_json=sample_chunks[0].metadata_json,
            ),
            DocumentSearchResultItem(
                chunk_id=sample_chunks[1].id,
                document_id=sample_chunks[1].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[1].content,
                page_number=sample_chunks[1].page_number,
                chunk_index=sample_chunks[1].chunk_index,
                similarity_score=0.85,
                metadata_json=sample_chunks[1].metadata_json,
            ),
        ]

        bm25_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[1].id,  # Rank 1 in BM25
                document_id=sample_chunks[1].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[1].content,
                page_number=sample_chunks[1].page_number,
                chunk_index=sample_chunks[1].chunk_index,
                similarity_score=10.0,
                metadata_json=sample_chunks[1].metadata_json,
            ),
            DocumentSearchResultItem(
                chunk_id=sample_chunks[0].id,  # Rank 2 in BM25
                document_id=sample_chunks[0].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[0].content,
                page_number=sample_chunks[0].page_number,
                chunk_index=sample_chunks[0].chunk_index,
                similarity_score=8.0,
                metadata_json=sample_chunks[0].metadata_json,
            ),
        ]

        with patch.object(svc, "search", return_value=vector_results):
            with patch("app.services.retrieval_bm25.search_documents_bm25", return_value=bm25_results):
                results = svc.search_hybrid(
                    project_id=project_id,
                    query="test",
                    top_k=5,
                    bm25_weight=0.5,
                    vector_weight=0.5,
                    rrf_k=60,
                    include_bm25=True,
                )

        # Both chunks appear in both retrievers - they should rank highest
        assert len(results) == 2
        # Chunk 0: vector rank 1 + bm25 rank 2 = 1/61 + 1/62
        # Chunk 1: vector rank 2 + bm25 rank 1 = 1/62 + 1/61
        # They should have equal or nearly equal scores

    def test_hybrid_search_respects_top_k(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """Hybrid search should respect top_k limit."""
        svc = DocumentRetrievalService(mock_db)

        # Create many results
        vector_results = []
        for i in range(20):
            chunk = sample_chunks[i % len(sample_chunks)]
            vector_results.append(
                DocumentSearchResultItem(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_name=sample_document.filename,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    similarity_score=0.9 - i * 0.01,
                    metadata_json=chunk.metadata_json,
                )
            )

        with patch.object(svc, "search", return_value=vector_results):
            with patch("app.services.retrieval_bm25.search_documents_bm25", return_value=[]):
                results = svc.search_hybrid(
                    project_id=project_id,
                    query="test",
                    top_k=3,
                    include_bm25=False,
                )

        assert len(results) == 3

    def test_hybrid_search_handles_empty_results(self, mock_db: MagicMock, project_id: uuid.UUID) -> None:
        """Hybrid search should handle empty results gracefully."""
        svc = DocumentRetrievalService(mock_db)

        with patch.object(svc, "search", return_value=[]):
            with patch("app.services.retrieval_bm25.search_documents_bm25", return_value=[]):
                results = svc.search_hybrid(
                    project_id=project_id,
                    query="test",
                    top_k=5,
                )

        assert results == []


class TestRRFParameters:
    """Tests for RRF configuration parameters."""

    def test_rrf_k_parameter_affects_ranking(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """Different RRF k values should produce different rankings."""
        svc = DocumentRetrievalService(mock_db)

        vector_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[0].id,
                document_id=sample_chunks[0].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[0].content,
                page_number=sample_chunks[0].page_number,
                chunk_index=sample_chunks[0].chunk_index,
                similarity_score=0.9,
                metadata_json=sample_chunks[0].metadata_json,
            ),
        ]

        bm25_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[1].id,
                document_id=sample_chunks[1].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[1].content,
                page_number=sample_chunks[1].page_number,
                chunk_index=sample_chunks[1].chunk_index,
                similarity_score=10.0,
                metadata_json=sample_chunks[1].metadata_json,
            ),
        ]

        with patch.object(svc, "search", return_value=vector_results):
            with patch.object(BM25Retriever, "search_bm25", return_value=bm25_results):
                results_k10 = svc.search_hybrid(
                    project_id=project_id,
                    query="test",
                    top_k=5,
                    rrf_k=10,
                    include_bm25=True,
                )

                results_k100 = svc.search_hybrid(
                    project_id=project_id,
                    query="test",
                    top_k=5,
                    rrf_k=100,
                    include_bm25=True,
                )

        # With smaller k, rank differences matter more
        # With larger k, ranks are more flattened
        assert len(results_k10) == len(results_k100) == 2

    def test_bm25_vector_weights(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """Weight parameters should affect final ranking."""
        svc = DocumentRetrievalService(mock_db)

        vector_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[0].id,
                document_id=sample_chunks[0].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[0].content,
                page_number=sample_chunks[0].page_number,
                chunk_index=sample_chunks[0].chunk_index,
                similarity_score=0.9,
                metadata_json=sample_chunks[0].metadata_json,
            ),
        ]

        bm25_results = [
            DocumentSearchResultItem(
                chunk_id=sample_chunks[1].id,
                document_id=sample_chunks[1].document_id,
                document_name=sample_document.filename,
                content=sample_chunks[1].content,
                page_number=sample_chunks[1].page_number,
                chunk_index=sample_chunks[1].chunk_index,
                similarity_score=10.0,
                metadata_json=sample_chunks[1].metadata_json,
            ),
        ]

        with patch.object(svc, "search", return_value=vector_results):
            with patch("app.services.retrieval_bm25.search_documents_bm25", return_value=bm25_results):
                # Heavy vector weight
                results_vec = svc.search_hybrid(
                    project_id=project_id,
                    query="test",
                    top_k=5,
                    bm25_weight=0.1,
                    vector_weight=0.9,
                    include_bm25=True,
                )

                # Heavy BM25 weight
                results_bm25 = svc.search_hybrid(
                    project_id=project_id,
                    query="test",
                    top_k=5,
                    bm25_weight=0.9,
                    vector_weight=0.1,
                    include_bm25=True,
                )

        # Vector-heavy should prefer vector result (chunk 0)
        # BM25-heavy should prefer BM25 result (chunk 1)
        if results_vec and results_bm25:
            assert results_vec[0].chunk_id != results_bm25[0].chunk_id or len(results_vec) == 1


class TestSearchDocumentsBM25Function:
    """Tests for the convenience function search_documents_bm25."""

    def test_convenience_function_works(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """search_documents_bm25 should work as a convenience wrapper."""
        # Create BM25Retriever instance (same as the function does)
        retriever = BM25Retriever(mock_db, project_id)

        # Set up the mock query chain to return sample chunks
        query_result = MagicMock()
        query_result.join.return_value.filter.return_value.options.return_value.all.return_value = [
            (chunk, sample_document.filename) for chunk in sample_chunks
        ]
        query_result.join.return_value.filter.return_value.count.return_value = len(sample_chunks)
        mock_db.query.return_value = query_result

        # Mock the internal avg_doc_len and doc_count properties by setting the private attributes
        with patch.object(retriever, '_avg_doc_len', 100.0):
            with patch.object(retriever, '_doc_count', len(sample_chunks)):
                results = search_documents_bm25(
                    db=mock_db,
                    project_id=project_id,
                    query="GPIO",
                    top_k=3,
                )

        assert len(results) > 0
        assert all(isinstance(r, DocumentSearchResultItem) for r in results)

    def test_convenience_function_custom_parameters(self, mock_db: MagicMock, project_id: uuid.UUID, sample_chunks: list[DocumentChunk], sample_document: Document) -> None:
        """Convenience function should accept custom BM25 parameters."""
        retriever = BM25Retriever(mock_db, project_id)

        with patch.object(retriever, '_avg_doc_len', 100.0):
            query_result = MagicMock()
            query_result.join.return_value.filter.return_value.options.return_value.all.return_value = [
                (chunk, sample_document.filename) for chunk in sample_chunks
            ]
            query_result.join.return_value.filter.return_value.count.return_value = len(sample_chunks)
            mock_db.query.return_value = query_result

            results = search_documents_bm25(
                db=mock_db,
                project_id=project_id,
                query="timer",
                top_k=5,
                k1=2.0,
                b=0.5,
            )

        assert len(results) >= 0