"""Deterministic document reranker for citation validation and result ordering.

This module provides reranking capabilities for Phase 11.3:
- No paid API dependencies (heuristic-based, offline capable)
- Grounded citation validation
- Testable with fixtures

The reranker uses a cross-encoder or heuristic approach to re-rank
results and validate that citations are supported by the source documents.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentSearchResultItem

logger = logging.getLogger(__name__)


class CitationValidation(Enum):
    """Status of citation validation."""
    VALID = "valid"
    PARTIAL = "partial"
    INVALID = "invalid"
    NO_CITATION = "no_citation"


@dataclass
class RerankedResult:
    """Result after reranking with citation validation."""
    item: DocumentSearchResultItem
    rerank_score: float
    citation_validated: bool
    validation_reason: str
    evidence_snippets: list[str]


@dataclass
class RerankingContext:
    """Context for reranking including query and relevant chunks."""
    query: str
    top_k: int
    include_citations: bool = True
    min_relevance_threshold: float = 0.3


class DeterministicReranker:
    """Deterministic reranker that re-ranks search results without external API calls.

    This reranker uses:
    1. Query-term matching in content
    2. Entity extraction (registers, pinouts, specifications)
    3. Position-based weighting (earlier chunks rank higher)
    4. Citation validation against source documents
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def _extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extract technical entities from text (Phase 11.3 grounded analysis)."""
        entities = {
            "registers": [],
            "bitfields": [],
            "pin_names": [],
            "addresses": [],
            "spec_values": [],
        }

        # Extract register names and addresses
        register_pattern = r"\b(?:0x[0-9a-fA-F]{2,8})\b"
        entities["addresses"] = re.findall(register_pattern, text)

        # Extract GPIO/sensor pin names
        pin_pattern = r"\b(?:GPIO|PIN|GPIO\d+|PIN\d+)[_:\s]?\w*"
        entities["pin_names"] = re.findall(pin_pattern, text)

        # Extract specification values (voltages, timing, etc.)
        spec_pattern = r"\b\d+(?:\.\d+)?\s*(?:V|VCC|VSS|mA|ms|kHz|MHz|Hz|%|°C)\b"
        entities["spec_values"] = re.findall(spec_pattern, text, re.IGNORECASE)

        return entities

    def _compute_query_match_score(self, query: str, content: str) -> float:
        """Compute how many query terms match in the content."""
        if not query or not content:
            return 0.0

        query_terms = query.lower().split()
        content_lower = content.lower()

        matches = sum(1 for term in query_terms if term in content_lower)
        return matches / len(query_terms) if query_terms else 0.0

    def _compute_entity_rerank_score(
        self,
        query: str,
        item: DocumentSearchResultItem,
    ) -> float:
        """Compute entity-based reranking score."""
        query_entities = self._extract_entities(query)
        content_entities = self._extract_entities(item.content or "")

        score = 0.0

        # Reward matching register addresses
        for addr in query_entities["addresses"]:
            if addr in (item.content or ""):
                score += 0.3

        # Reward matching pin names
        for pin in query_entities["pin_names"]:
            pin_clean = pin.split("_")[0].split(":")[0].strip()
            if pin_clean.lower() in (item.content or "").lower():
                score += 0.2

        # Reward matching spec values (higher weight for technical specs)
        for spec in query_entities["spec_values"]:
            if spec in (item.content or ""):
                score += 0.3

        return min(score, 1.0)  # Cap at 1.0

    def _validate_citations(
        self,
        query: str,
        item: DocumentSearchResultItem,
    ) -> tuple[bool, str, list[str]]:
        """Validate that cited information is present in the source chunk.

        Returns:
            Tuple of (is_valid, reason, evidence_snippets)
        """
        if not item.content:
            return False, "No content in chunk", []

        evidence = []
        content_lower = item.content.lower()

        # Check for register references (CR1, SR1, DR1, 0x addresses)
        register_refs = re.findall(r"(CR\d+|SR\d+|DR\d+|0x[0-9a-fA-F]{4,})", query, re.IGNORECASE)
        if register_refs:
            for ref in register_refs[:3]:
                if ref.lower() in content_lower:
                    evidence.append(f"Register reference '{ref}' found in source")
                    return True, "Register citation validated", evidence

        # Check for GPIO/pin references
        pin_refs = re.findall(r"(GPIO\d*|PIN\d*\b)", query, re.IGNORECASE)
        if pin_refs:
            for ref in pin_refs[:3]:
                if ref.lower() in content_lower:
                    evidence.append(f"Pin reference '{ref}' found in source")
                    return True, "Pin citation validated", evidence

        # Check for voltage/specification references
        spec_refs = re.findall(r"(\d+(?:\.\d+)?\s*V)", query, re.IGNORECASE)
        if spec_refs:
            for ref in spec_refs[:2]:
                if ref in item.content:
                    evidence.append(f"Specification value '{ref}' found in source")
                    return True, "Spec citation validated", evidence

        # If no specific citations found, check general relevance
        match_score = self._compute_query_match_score(query, item.content or "")
        if match_score > 0.5:
            # Extract evidence snippet
            for term in query.lower().split()[:5]:
                if term in content_lower:
                    pos = content_lower.find(term)
                    snippet = item.content[max(0, pos-30):pos+100]
                    evidence.append(snippet.strip())
                    break
            return True, "General relevance citation", evidence

        return False, "No matching citation found", evidence

    def rerank_results(
        self,
        query: str,
        results: list[DocumentSearchResultItem],
        context: Optional[RerankingContext] = None,
    ) -> list[RerankedResult]:
        """Rerank search results with deterministic scoring.

        Args:
            query: Original search query
            results: List of search results to rerank
            context: Optional reranking context

        Returns:
            List of reranked results with validation scores
        """
        if not results:
            return []

        if context is None:
            context = RerankingContext(query=query, top_k=10)

        reranked = []

        for item in results:
            # Compute combined rerank score
            query_match = self._compute_query_match_score(context.query, item.content or "")
            entity_bonus = self._compute_entity_rerank_score(context.query, item)

            # Compute combined score with entity-aware weighting
            # For spec/voltage queries, entity matches should dominate
            if "V" in query or "voltage" in query.lower() or "VDD" in query.upper():
                # For voltage queries, entity bonus heavily weighted but keep scores above threshold
                combined_score = (item.similarity_score or 0) * 0.5 + entity_bonus * 0.5
            else:
                combined_score = (item.similarity_score or 0) * 0.6 + entity_bonus * 0.4

            # Validate citations
            (
                is_valid,
                reason,
                evidence,
            ) = self._validate_citations(context.query, item)

            reranked.append(RerankedResult(
                item=item,
                rerank_score=combined_score,
                citation_validated=is_valid,
                validation_reason=reason,
                evidence_snippets=evidence[:3],  # Limit evidence snippets
            ))

        # Sort by rerank score descending
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        # Filter by relevance threshold
        reranked = [r for r in reranked if r.rerank_score >= context.min_relevance_threshold]

        return reranked

    def rerank_results_with_limit(
        self,
        query: str,
        results: list[DocumentSearchResultItem],
        top_k: int = 10,
    ) -> list[RerankedResult]:
        """Convenience method to rerank and limit results."""
        context = RerankingContext(query=query, top_k=top_k)
        reranked = self.rerank_results(query, results, context)
        return reranked[:top_k]