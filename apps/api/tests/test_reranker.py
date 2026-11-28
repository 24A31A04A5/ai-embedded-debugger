"""Tests for Phase 11.3 — Deterministic Reranker with Citation Validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentSearchResultItem
from app.services.reranker import (
    CitationValidation,
    DeterministicReranker,
    RerankedResult,
    RerankingContext,
)


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=Session)


@pytest.fixture
def sample_results() -> list[DocumentSearchResultItem]:
    """Create sample search results for reranking tests."""
    doc_id = uuid.uuid4()
    results = []

    contents = [
        "ESP32 GPIO4 register address 0x3FF44004 controls pin direction and capacitive touch",
        "STM32 TIM2 CR1 register 0x40000000 enables counter and sets prescaler value",
        "GPIO pin configuration: PA5 as output push-pull for LED control with 50MHz speed",
        "Voltage specification: VDD 3.3V typical, absolute maximum 3.6V, current 40mA per pin",
        "I2C SDA on GPIO21 requires external 4.7k pull-up resistor to VDD",
        "ADC1 channel 0 on GPIO36 reads analog voltage 0-3.3V with 12-bit resolution",
    ]

    for i, content in enumerate(contents):
        chunk_id = uuid.uuid4()
        result = DocumentSearchResultItem(
            chunk_id=chunk_id,
            document_id=doc_id,
            document_name="mcu_datasheet.pdf",
            content=content,
            page_number=i + 1,
            chunk_index=i,
            similarity_score=0.8 - i * 0.05,
            metadata_json={"section": f"Section {i+1}"},
        )
        results.append(result)

    return results


class TestEntityExtraction:
    """Tests for entity extraction from text."""

    def test_extract_register_addresses(self, mock_db: MagicMock) -> None:
        """Should extract register addresses like 0x3FF44004."""
        reranker = DeterministicReranker(mock_db)
        text = "Register at 0x3FF44004 and 0x40000000 control GPIO"
        entities = reranker._extract_entities(text)
        assert "0x3FF44004" in entities["addresses"]
        assert "0x40000000" in entities["addresses"]

    def test_extract_pin_names(self, mock_db: MagicMock) -> None:
        """Should extract GPIO/PIN references."""
        reranker = DeterministicReranker(mock_db)
        text = "GPIO4 and PIN5 are configured as outputs"
        entities = reranker._extract_entities(text)
        assert any("GPIO4" in p for p in entities["pin_names"])
        assert any("PIN5" in p for p in entities["pin_names"])

    def test_extract_spec_values(self, mock_db: MagicMock) -> None:
        """Should extract voltage, timing, and current specifications."""
        reranker = DeterministicReranker(mock_db)
        text = "VDD 3.3V, 40mA current, 50MHz frequency, 25°C temperature"
        entities = reranker._extract_entities(text)
        assert "3.3V" in entities["spec_values"]
        assert "40mA" in entities["spec_values"]
        assert "50MHz" in entities["spec_values"]

    def test_empty_text_returns_empty_entities(self, mock_db: MagicMock) -> None:
        """Empty text should return empty entity lists."""
        reranker = DeterministicReranker(mock_db)
        entities = reranker._extract_entities("")
        assert all(len(v) == 0 for v in entities.values())


class TestQueryMatchScore:
    """Tests for query term matching score."""

    def test_exact_match_returns_high_score(self, mock_db: MagicMock) -> None:
        """Exact query terms in content should score high."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO register"
        content = "GPIO register address 0x3FF44004 controls direction"
        score = reranker._compute_query_match_score(query, content)
        assert score > 0.5

    def test_no_match_returns_zero(self, mock_db: MagicMock) -> None:
        """No matching terms should return zero."""
        reranker = DeterministicReranker(mock_db)
        query = "USB controller"
        content = "GPIO register address 0x3FF44004"
        score = reranker._compute_query_match_score(query, content)
        assert score == 0.0

    def test_partial_match(self, mock_db: MagicMock) -> None:
        """Partial term matches should give proportional score."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO timer register"
        content = "GPIO register address 0x3FF44004"
        score = reranker._compute_query_match_score(query, content)
        assert 0.0 < score < 1.0


class TestEntityRerankScore:
    """Tests for entity-based reranking bonus."""

    def test_matching_register_address_bonus(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Matching register address in query and content should give bonus."""
        reranker = DeterministicReranker(mock_db)
        query = "register 0x3FF44004"
        item = sample_results[0]  # Contains 0x3FF44004
        score = reranker._compute_entity_rerank_score(query, item)
        assert score >= 0.3

    def test_matching_pin_name_bonus(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Matching pin name should give bonus."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO4 pin"
        item = sample_results[0]  # Contains GPIO4
        score = reranker._compute_entity_rerank_score(query, item)
        assert score >= 0.2

    def test_matching_spec_value_bonus(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Matching specification value should give bonus."""
        reranker = DeterministicReranker(mock_db)
        query = "3.3V voltage"
        item = sample_results[3]  # Contains 3.3V
        score = reranker._compute_entity_rerank_score(query, item)
        assert score >= 0.1

    def test_no_entity_match_zero_bonus(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """No entity matches should return zero bonus."""
        reranker = DeterministicReranker(mock_db)
        query = "USB endpoint"
        item = sample_results[0]
        score = reranker._compute_entity_rerank_score(query, item)
        assert score == 0.0

    def test_score_capped_at_one(self, mock_db: MagicMock) -> None:
        """Entity bonus should be capped at 1.0."""
        reranker = DeterministicReranker(mock_db)
        # Create item with many matching entities
        item = DocumentSearchResultItem(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_name="test.pdf",
            content="0x1234 0x5678 0x9ABC GPIO1 GPIO2 GPIO3 1.0V 2.0V 3.0V",
            page_number=1,
            chunk_index=0,
            similarity_score=0.5,
            metadata_json={},
        )
        query = "0x1234 0x5678 0x9ABC GPIO1 GPIO2 GPIO3 1.0V 2.0V 3.0V"
        score = reranker._compute_entity_rerank_score(query, item)
        assert score <= 1.0


class TestCitationValidation:
    """Tests for citation validation against source chunks."""

    def test_register_citation_validated(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Register references in query should be validated against content."""
        reranker = DeterministicReranker(mock_db)
        query = "CR1 register configuration"
        item = sample_results[1]  # Contains CR1 register
        is_valid, reason, evidence = reranker._validate_citations(query, item)
        assert is_valid is True
        assert "Register citation validated" in reason
        assert len(evidence) > 0

    def test_pin_citation_validated(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Pin references should be validated."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO4 pin setup"
        item = sample_results[0]  # Contains GPIO4
        is_valid, reason, evidence = reranker._validate_citations(query, item)
        assert is_valid is True
        assert "Pin citation validated" in reason

    def test_voltage_citation_validated(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Voltage specification citations should be validated."""
        reranker = DeterministicReranker(mock_db)
        query = "3.3V supply voltage"
        item = sample_results[3]  # Contains 3.3V
        is_valid, reason, evidence = reranker._validate_citations(query, item)
        assert is_valid is True
        assert "Spec citation validated" in reason

    def test_general_relevance_citation(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """High general relevance should pass as citation."""
        reranker = DeterministicReranker(mock_db)
        # Use a query that has high relevance but doesn't match specific patterns
        # (no CR1, SRx, DRx, 0x, or pin name references)
        query = "direction capacitive touch"
        item = sample_results[0]  # Contains these terms but no specific patterns
        is_valid, reason, evidence = reranker._validate_citations(query, item)
        assert is_valid is True
        assert "General relevance citation" in reason

    def test_no_citation_invalid(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Unrelated query should fail citation validation."""
        reranker = DeterministicReranker(mock_db)
        query = "USB PHY configuration"
        item = sample_results[0]  # GPIO content
        is_valid, reason, evidence = reranker._validate_citations(query, item)
        assert is_valid is False
        assert "No matching citation found" in reason

    def test_empty_content_invalid(self, mock_db: MagicMock) -> None:
        """Empty content should fail validation."""
        reranker = DeterministicReranker(mock_db)
        item = DocumentSearchResultItem(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_name="test.pdf",
            content="",
            page_number=1,
            chunk_index=0,
            similarity_score=0.5,
            metadata_json={},
        )
        is_valid, reason, evidence = reranker._validate_citations("test query", item)
        assert is_valid is False
        assert "No content in chunk" in reason


class TestRerankResults:
    """Tests for the main rerank_results method."""

    def test_rerank_returns_reranked_results(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """rerank_results should return list of RerankedResult."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO register"
        results = reranker.rerank_results(query, sample_results)

        assert len(results) > 0
        assert all(isinstance(r, RerankedResult) for r in results)
        assert all(hasattr(r, "rerank_score") for r in results)
        assert all(hasattr(r, "citation_validated") for r in results)
        assert all(hasattr(r, "validation_reason") for r in results)
        assert all(hasattr(r, "evidence_snippets") for r in results)

    def test_rerank_sorts_by_score_descending(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Results should be sorted by rerank_score descending."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO register"
        results = reranker.rerank_results(query, sample_results)

        scores = [r.rerank_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_filters_by_relevance_threshold(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Results below min_relevance_threshold should be filtered out."""
        reranker = DeterministicReranker(mock_db)
        query = "unrelated query xyz"
        context = RerankingContext(query=query, top_k=10, min_relevance_threshold=0.5)
        results = reranker.rerank_results(query, sample_results, context)

        # All results should have score >= 0.5 or be empty
        assert all(r.rerank_score >= 0.5 for r in results)

    def test_rerank_respects_top_k_limit(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """rerank_results_with_limit should respect top_k."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO"
        results = reranker.rerank_results_with_limit(query, sample_results, top_k=3)

        assert len(results) <= 3

    def test_rerank_empty_input_returns_empty(self, mock_db: MagicMock) -> None:
        """Empty input should return empty list."""
        reranker = DeterministicReranker(mock_db)
        results = reranker.rerank_results("query", [])
        assert results == []

    def test_rerank_preserves_original_item(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Reranked result should preserve original search result item."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO register"
        results = reranker.rerank_results(query, sample_results)

        assert len(results) > 0
        assert results[0].item is not None
        assert isinstance(results[0].item, DocumentSearchResultItem)
        assert results[0].item.chunk_id == sample_results[0].chunk_id or results[0].item.chunk_id in [r.chunk_id for r in sample_results]


class TestRerankingContext:
    """Tests for RerankingContext dataclass."""

    def test_default_context(self, mock_db: MagicMock) -> None:
        """Default context should have sensible defaults."""
        context = RerankingContext(query="test", top_k=10)
        assert context.query == "test"
        assert context.top_k == 10
        assert context.include_citations is True
        assert context.min_relevance_threshold == 0.3

    def test_custom_context(self, mock_db: MagicMock) -> None:
        """Custom context parameters should be respected."""
        context = RerankingContext(
            query="test",
            top_k=5,
            include_citations=False,
            min_relevance_threshold=0.5,
        )
        assert context.top_k == 5
        assert context.include_citations is False
        assert context.min_relevance_threshold == 0.5


class TestCitationValidationEnum:
    """Tests for CitationValidation enum."""

    def test_enum_values(self) -> None:
        """CitationValidation should have expected values."""
        assert CitationValidation.VALID.value == "valid"
        assert CitationValidation.PARTIAL.value == "partial"
        assert CitationValidation.INVALID.value == "invalid"
        assert CitationValidation.NO_CITATION.value == "no_citation"


class TestRerankedResultDataclass:
    """Tests for RerankedResult dataclass."""

    def test_reranked_result_creation(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """RerankedResult should be creatable with all fields."""
        item = sample_results[0]
        result = RerankedResult(
            item=item,
            rerank_score=0.85,
            citation_validated=True,
            validation_reason="Test reason",
            evidence_snippets=["snippet 1", "snippet 2"],
        )
        assert result.item == item
        assert result.rerank_score == 0.85
        assert result.citation_validated is True
        assert result.validation_reason == "Test reason"
        assert len(result.evidence_snippets) == 2


class TestRerankerIntegration:
    """Integration-style tests for reranker with realistic scenarios."""

    def test_embedded_query_reranking(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Typical embedded query should rerank register/spec content higher."""
        reranker = DeterministicReranker(mock_db)
        query = "TIM2 CR1 register 0x40000000 prescaler"
        results = reranker.rerank_results(query, sample_results)

        # Result 1 (TIM2 CR1) should rank highest
        assert results[0].item.content is not None
        assert "TIM2" in results[0].item.content or "CR1" in results[0].item.content

    def test_gpio_query_prefers_gpio_chunks(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """GPIO query should prefer chunks with GPIO content."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO4 capacitive touch setup"
        results = reranker.rerank_results(query, sample_results)

        # Result 0 (GPIO4) should rank highest
        assert "GPIO4" in results[0].item.content

    def test_voltage_query_prefers_spec_chunks(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Voltage query should prefer specification chunks."""
        reranker = DeterministicReranker(mock_db)
        query = "VDD 3.3V maximum voltage"
        results = reranker.rerank_results(query, sample_results)

        # Result 3 (voltage spec) should rank highest
        assert "3.3V" in results[0].item.content

    def test_citation_evidence_included(self, mock_db: MagicMock, sample_results: list[DocumentSearchResultItem]) -> None:
        """Validated citations should include evidence snippets."""
        reranker = DeterministicReranker(mock_db)
        query = "GPIO register"
        results = reranker.rerank_results(query, sample_results)

        # At least top result should have evidence
        assert len(results[0].evidence_snippets) > 0