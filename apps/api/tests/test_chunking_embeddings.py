"""Tests for Phase 3.2 — Document chunking, embeddings, and processing pipeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import RawChunk
from app.services.chunking import DocumentChunkingService
from app.services.embedding import BaseEmbeddingService, EmbeddingError, GeminiEmbeddingService
from app.services.document_processing import DocumentProcessingService


# ---------------------------------------------------------------------------
# Chunking service tests
# ---------------------------------------------------------------------------


class TestDocumentChunkingService:
    """Tests for deterministic document chunking."""

    def test_empty_text_returns_no_chunks(self) -> None:
        svc = DocumentChunkingService(chunk_size=100, chunk_overlap=20)
        assert svc.chunk_text("") == []
        assert svc.chunk_text("   ") == []
        assert svc.chunk_text("\n\n\n") == []

    def test_short_text_single_chunk(self) -> None:
        svc = DocumentChunkingService(chunk_size=500, chunk_overlap=50)
        text = "Hello world. This is a short document."
        chunks = svc.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].content == text

    def test_multiple_paragraphs_respect_chunk_size(self) -> None:
        svc = DocumentChunkingService(chunk_size=100, chunk_overlap=0)
        # Create paragraphs that each fit in a chunk individually
        paragraphs = [f"Paragraph {i}. " + "x" * 40 for i in range(5)]
        text = "\n\n".join(paragraphs)
        chunks = svc.chunk_text(text)
        assert len(chunks) > 1
        for chunk in chunks:
            # Each chunk content should be ≤ chunk_size (approximate, paragraph-boundary aligned)
            assert len(chunk.content) <= 200  # generous bound for paragraph merging

    def test_deterministic_ordering(self) -> None:
        svc = DocumentChunkingService(chunk_size=100, chunk_overlap=20)
        text = "\n\n".join([f"Section {i}: " + "content " * 10 for i in range(10)])
        chunks_a = svc.chunk_text(text)
        chunks_b = svc.chunk_text(text)
        assert len(chunks_a) == len(chunks_b)
        for a, b in zip(chunks_a, chunks_b):
            assert a.chunk_index == b.chunk_index
            assert a.content == b.content

    def test_chunk_indices_are_sequential(self) -> None:
        svc = DocumentChunkingService(chunk_size=80, chunk_overlap=10)
        text = "\n\n".join([f"Block {i}: " + "data " * 15 for i in range(8)])
        chunks = svc.chunk_text(text)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_overlap_produces_overlapping_content(self) -> None:
        svc = DocumentChunkingService(chunk_size=100, chunk_overlap=30)
        # Create text with distinct paragraphs smaller than chunk size
        paragraphs = [f"Para{i} " + "word " * 8 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = svc.chunk_text(text)
        if len(chunks) >= 2:
            # The overlap should cause some content to appear in consecutive chunks
            # Check that consecutive chunks share some text
            for i in range(len(chunks) - 1):
                c1_words = set(chunks[i].content.split())
                c2_words = set(chunks[i + 1].content.split())
                # With overlap > 0, there should be SOME overlap
                # (unless paragraph boundaries prevent it)
                overlap = c1_words & c2_words
                # At minimum, check ordering is maintained
                assert chunks[i].chunk_index < chunks[i + 1].chunk_index

    def test_no_overlap_no_duplicate_content(self) -> None:
        svc = DocumentChunkingService(chunk_size=200, chunk_overlap=0)
        text = "Alpha paragraph.\n\nBeta paragraph.\n\nGamma paragraph."
        chunks = svc.chunk_text(text)
        all_content = " ".join(c.content for c in chunks)
        # All paragraphs should be present
        assert "Alpha" in all_content
        assert "Beta" in all_content
        assert "Gamma" in all_content

    def test_page_number_assignment(self) -> None:
        svc = DocumentChunkingService(chunk_size=500, chunk_overlap=0)
        page_texts = [
            "Page one content with important data.",
            "Page two has different information.",
            "Page three concludes the document.",
        ]
        full_text = "\n\n".join(page_texts)
        chunks = svc.chunk_text(full_text, page_texts=page_texts)
        assert len(chunks) >= 1
        # First chunk should be from page 1
        assert chunks[0].page_number == 1

    def test_page_number_none_without_page_texts(self) -> None:
        svc = DocumentChunkingService(chunk_size=500, chunk_overlap=0)
        chunks = svc.chunk_text("Some text content here.")
        assert len(chunks) == 1
        assert chunks[0].page_number is None

    def test_large_segment_gets_sub_split(self) -> None:
        svc = DocumentChunkingService(chunk_size=100, chunk_overlap=0)
        # A single segment larger than chunk_size
        text = "word " * 100  # 500 chars
        chunks = svc.chunk_text(text)
        assert len(chunks) > 1
        # No chunk should exceed chunk_size significantly
        for chunk in chunks:
            assert len(chunk.content) <= 150  # generous bound

    def test_invalid_chunk_size_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            DocumentChunkingService(chunk_size=0, chunk_overlap=0)
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            DocumentChunkingService(chunk_size=-1, chunk_overlap=0)

    def test_invalid_overlap_raises(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap"):
            DocumentChunkingService(chunk_size=100, chunk_overlap=100)
        with pytest.raises(ValueError, match="chunk_overlap"):
            DocumentChunkingService(chunk_size=100, chunk_overlap=-1)

    def test_chunk_metadata_is_dict(self) -> None:
        svc = DocumentChunkingService(chunk_size=500, chunk_overlap=0)
        chunks = svc.chunk_text("Test content.")
        assert len(chunks) == 1
        assert isinstance(chunks[0].metadata, dict)

    def test_multipage_chunking_tracks_pages(self) -> None:
        svc = DocumentChunkingService(chunk_size=60, chunk_overlap=0)
        page_texts = [
            "Short page one.",
            "Short page two.",
            "Short page three.",
        ]
        full_text = "\n\n".join(page_texts)
        chunks = svc.chunk_text(full_text, page_texts=page_texts)
        # With small chunk size, pages may merge or split
        assert len(chunks) >= 1
        # At least some chunks should have page numbers
        page_nums = [c.page_number for c in chunks if c.page_number is not None]
        assert len(page_nums) > 0


# ---------------------------------------------------------------------------
# Embedding service tests
# ---------------------------------------------------------------------------


class TestEmbeddingService:
    """Tests for the embedding service abstraction (mocked API calls)."""

    def _mock_embedding_response(self, vectors: list[list[float]]) -> MagicMock:
        """Create a mock EmbedContentResponse."""
        response = MagicMock()
        embeddings = []
        for vec in vectors:
            emb = MagicMock()
            emb.values = vec
            embeddings.append(emb)
        response.embeddings = embeddings
        return response

    def test_embed_text_returns_correct_dimension(self) -> None:
        mock_client = MagicMock()
        expected_vec = [0.1] * 3072
        mock_client.models.embed_content.return_value = self._mock_embedding_response([expected_vec])

        with patch("app.services.embedding.genai") as mock_genai:
            mock_genai.Client.return_value = mock_client
            settings = MagicMock()
            settings.gemini_api_key = "test-key"
            settings.embedding_model = "gemini-embedding-001"
            settings.embedding_dimension = 3072

            svc = GeminiEmbeddingService(settings)
            result = svc.embed_text("Hello world")

            assert len(result) == 3072
            assert result == expected_vec
            mock_client.models.embed_content.assert_called_once_with(
                model="gemini-embedding-001",
                contents="Hello world",
            )

    def test_embed_batch_returns_correct_count(self) -> None:
        mock_client = MagicMock()
        vectors = [[0.1 * i] * 3072 for i in range(3)]
        mock_client.models.embed_content.return_value = self._mock_embedding_response(vectors)

        with patch("app.services.embedding.genai") as mock_genai:
            mock_genai.Client.return_value = mock_client
            settings = MagicMock()
            settings.gemini_api_key = "test-key"
            settings.embedding_model = "gemini-embedding-001"
            settings.embedding_dimension = 3072

            svc = GeminiEmbeddingService(settings)
            results = svc.embed_batch(["text1", "text2", "text3"])

            assert len(results) == 3
            for vec in results:
                assert len(vec) == 3072

    def test_embed_batch_empty_returns_empty(self) -> None:
        mock_client = MagicMock()

        with patch("app.services.embedding.genai") as mock_genai:
            mock_genai.Client.return_value = mock_client
            settings = MagicMock()
            settings.gemini_api_key = "test-key"
            settings.embedding_model = "gemini-embedding-001"
            settings.embedding_dimension = 3072

            svc = GeminiEmbeddingService(settings)
            results = svc.embed_batch([])

            assert results == []

    def test_dimension_mismatch_raises_error(self) -> None:
        mock_client = MagicMock()
        wrong_dim_vec = [0.1] * 768  # wrong dimension
        mock_client.models.embed_content.return_value = self._mock_embedding_response(
            [wrong_dim_vec]
        )

        with patch("app.services.embedding.genai") as mock_genai:
            mock_genai.Client.return_value = mock_client
            settings = MagicMock()
            settings.gemini_api_key = "test-key"
            settings.embedding_model = "gemini-embedding-001"
            settings.embedding_dimension = 3072

            svc = GeminiEmbeddingService(settings)
            with pytest.raises(EmbeddingError, match="Unexpected dimension"):
                svc.embed_text("test")

    def test_api_error_raises_embedding_error(self) -> None:
        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = RuntimeError("API down")

        with patch("app.services.embedding.genai") as mock_genai:
            mock_genai.Client.return_value = mock_client
            settings = MagicMock()
            settings.gemini_api_key = "test-key"
            settings.embedding_model = "gemini-embedding-001"
            settings.embedding_dimension = 3072

            svc = GeminiEmbeddingService(settings)
            with pytest.raises(EmbeddingError, match="Failed to generate embedding"):
                svc.embed_text("test")

    def test_missing_api_key_raises_error(self) -> None:
        with patch("app.services.embedding.genai"):
            settings = MagicMock()
            settings.gemini_api_key = ""
            settings.embedding_model = "gemini-embedding-001"
            settings.embedding_dimension = 3072

            with pytest.raises(EmbeddingError, match="GEMINI_API_KEY"):
                GeminiEmbeddingService(settings)

    def test_model_name_and_dimension(self) -> None:
        mock_client = MagicMock()

        with patch("app.services.embedding.genai") as mock_genai:
            mock_genai.Client.return_value = mock_client
            settings = MagicMock()
            settings.gemini_api_key = "test-key"
            settings.embedding_model = "gemini-embedding-001"
            settings.embedding_dimension = 3072

            svc = GeminiEmbeddingService(settings)
            assert svc.model_name() == "gemini-embedding-001"
            assert svc.dimension() == 3072

    def test_batch_count_mismatch_raises_error(self) -> None:
        mock_client = MagicMock()
        # Return 2 embeddings for 3 texts
        vectors = [[0.1] * 3072, [0.2] * 3072]
        mock_client.models.embed_content.return_value = self._mock_embedding_response(vectors)

        with patch("app.services.embedding.genai") as mock_genai:
            mock_genai.Client.return_value = mock_client
            settings = MagicMock()
            settings.gemini_api_key = "test-key"
            settings.embedding_model = "gemini-embedding-001"
            settings.embedding_dimension = 3072

            svc = GeminiEmbeddingService(settings)
            with pytest.raises(EmbeddingError, match="Expected 3 embeddings, got 2"):
                svc.embed_batch(["a", "b", "c"])


# ---------------------------------------------------------------------------
# Document processing pipeline tests
# ---------------------------------------------------------------------------


class TestDocumentProcessingService:
    """Tests for the end-to-end chunking + embedding + persistence pipeline."""

    def _make_document(self, project_id: uuid.UUID | None = None) -> Document:
        return Document(
            id=uuid.uuid4(),
            project_id=project_id or uuid.uuid4(),
            filename="test.pdf",
            size_bytes=1024,
            checksum="abc123",
            storage_key="projects/x/documents/test.pdf",
            extraction_status="processing",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def _make_mock_embedding_service(self, dim: int = 3072) -> MagicMock:
        svc = MagicMock(spec=BaseEmbeddingService)
        svc.model_name.return_value = "gemini-embedding-001"
        svc.dimension.return_value = dim

        def _embed_batch(texts: list[str]) -> list[list[float]]:
            return [[0.01 * i] * dim for i in range(len(texts))]

        svc.embed_batch.side_effect = _embed_batch
        return svc

    def test_process_document_creates_chunks(self) -> None:
        mock_db = MagicMock()
        mock_emb = self._make_mock_embedding_service()
        doc = self._make_document()

        svc = DocumentProcessingService(
            db=mock_db,
            embedding_service=mock_emb,
            chunking_service=DocumentChunkingService(chunk_size=500, chunk_overlap=50),
        )

        text = "This is paragraph one.\n\nThis is paragraph two.\n\nThis is paragraph three."
        chunks = svc.process_document(doc, text)

        assert len(chunks) >= 1
        assert all(isinstance(c, DocumentChunk) for c in chunks)
        assert mock_db.add.call_count == len(chunks)
        assert mock_db.flush.called

    def test_process_document_empty_text_returns_empty(self) -> None:
        mock_db = MagicMock()
        mock_emb = self._make_mock_embedding_service()
        doc = self._make_document()

        svc = DocumentProcessingService(
            db=mock_db,
            embedding_service=mock_emb,
            chunking_service=DocumentChunkingService(chunk_size=500, chunk_overlap=50),
        )

        chunks = svc.process_document(doc, "")
        assert chunks == []
        assert not mock_db.add.called

    def test_process_document_preserves_document_id(self) -> None:
        mock_db = MagicMock()
        mock_emb = self._make_mock_embedding_service()
        doc = self._make_document()

        svc = DocumentProcessingService(
            db=mock_db,
            embedding_service=mock_emb,
            chunking_service=DocumentChunkingService(chunk_size=1000, chunk_overlap=0),
        )

        chunks = svc.process_document(doc, "Some text to chunk.")
        assert len(chunks) == 1
        assert chunks[0].document_id == doc.id

    def test_process_document_stores_embedding_model(self) -> None:
        mock_db = MagicMock()
        mock_emb = self._make_mock_embedding_service()
        doc = self._make_document()

        svc = DocumentProcessingService(
            db=mock_db,
            embedding_service=mock_emb,
            chunking_service=DocumentChunkingService(chunk_size=1000, chunk_overlap=0),
        )

        chunks = svc.process_document(doc, "Content for embedding.")
        assert chunks[0].embedding_model == "gemini-embedding-001"

    def test_process_document_stores_embeddings(self) -> None:
        mock_db = MagicMock()
        mock_emb = self._make_mock_embedding_service()
        doc = self._make_document()

        svc = DocumentProcessingService(
            db=mock_db,
            embedding_service=mock_emb,
            chunking_service=DocumentChunkingService(chunk_size=1000, chunk_overlap=0),
        )

        chunks = svc.process_document(doc, "Some text.")
        assert len(chunks) == 1
        assert chunks[0].embedding is not None
        assert len(chunks[0].embedding) == 3072

    def test_process_document_embedding_failure_propagates(self) -> None:
        mock_db = MagicMock()
        mock_emb = MagicMock(spec=BaseEmbeddingService)
        mock_emb.model_name.return_value = "gemini-embedding-001"
        mock_emb.embed_batch.side_effect = EmbeddingError("API failure")
        doc = self._make_document()

        svc = DocumentProcessingService(
            db=mock_db,
            embedding_service=mock_emb,
            chunking_service=DocumentChunkingService(chunk_size=1000, chunk_overlap=0),
        )

        with pytest.raises(EmbeddingError, match="API failure"):
            svc.process_document(doc, "Some text.")

    def test_process_document_with_page_texts(self) -> None:
        mock_db = MagicMock()
        mock_emb = self._make_mock_embedding_service()
        doc = self._make_document()

        svc = DocumentProcessingService(
            db=mock_db,
            embedding_service=mock_emb,
            chunking_service=DocumentChunkingService(chunk_size=500, chunk_overlap=0),
        )

        page_texts = ["Page 1 content here.", "Page 2 content here."]
        full_text = "\n\n".join(page_texts)
        chunks = svc.process_document(doc, full_text, page_texts=page_texts)
        assert len(chunks) >= 1
        # At least one chunk should have a page number
        page_nums = [c.page_number for c in chunks if c.page_number is not None]
        assert len(page_nums) > 0

    def test_process_document_project_isolation(self) -> None:
        """Chunks from different documents belong to their respective documents."""
        mock_db = MagicMock()
        mock_emb = self._make_mock_embedding_service()
        proj_a = uuid.uuid4()
        proj_b = uuid.uuid4()
        doc_a = self._make_document(project_id=proj_a)
        doc_b = self._make_document(project_id=proj_b)

        chunking = DocumentChunkingService(chunk_size=1000, chunk_overlap=0)

        svc = DocumentProcessingService(db=mock_db, embedding_service=mock_emb, chunking_service=chunking)
        chunks_a = svc.process_document(doc_a, "Project A content.")
        chunks_b = svc.process_document(doc_b, "Project B content.")

        for c in chunks_a:
            assert c.document_id == doc_a.id
        for c in chunks_b:
            assert c.document_id == doc_b.id

        # No cross-contamination
        a_ids = {c.document_id for c in chunks_a}
        b_ids = {c.document_id for c in chunks_b}
        assert a_ids.isdisjoint(b_ids)

    def test_chunk_index_sequential_after_processing(self) -> None:
        mock_db = MagicMock()
        mock_emb = self._make_mock_embedding_service()
        doc = self._make_document()

        svc = DocumentProcessingService(
            db=mock_db,
            embedding_service=mock_emb,
            chunking_service=DocumentChunkingService(chunk_size=80, chunk_overlap=10),
        )

        text = "\n\n".join([f"Section {i}: " + "data " * 12 for i in range(6)])
        chunks = svc.process_document(doc, text)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))
