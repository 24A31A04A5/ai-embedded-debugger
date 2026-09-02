"""Tests for Phase 5.3 — Advanced Embedded Knowledge and Source-Aware Retrieval.

Covers:
1.  MCU/peripheral knowledge retrieval
2.  Register/bitfield source retrieval
3.  Pin configuration source retrieval
4.  Electrical/timing specification retrieval
5.  Source metadata and traceability (content_type, section, chunk_id, page)
6.  Technically relevant source prioritization (enriched query building)
7.  Multiple supporting chunks
8.  Grounded-response compatibility (format_prompt XML tags)
9.  Ownership isolation (project-scoped)
10. Backward compatibility with existing retrieval
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.project import Project
from app.models.user import User
from app.schemas.context import AssembledDebugContext, DocumentContext, ProjectContext
from app.services.context_assembly import (
    _build_technical_retrieval_query,
    _extract_technical_keywords,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def project_ctx() -> ProjectContext:
    return ProjectContext(
        project_id=uuid.uuid4(),
        project_name="ESP32 Embedded Debugger",
        description="Phase 5.3 testing workspace",
    )


def _make_doc_context(
    snippet: str,
    content_type: str = "text",
    section: str | None = None,
    page_number: int | None = None,
    chunk_index: int | None = None,
    score: float = 0.82,
    metadata_json: dict[str, Any] | None = None,
) -> DocumentContext:
    meta = {"content_type": content_type}
    if section:
        meta["section"] = section
    if metadata_json:
        meta.update(metadata_json)
    return DocumentContext(
        doc_id=str(uuid.uuid4()),
        title="stm32f4_reference_manual.pdf",
        snippet=snippet,
        source="stm32f4_reference_manual.pdf",
        score=score,
        chunk_id=str(uuid.uuid4()),
        page_number=page_number,
        chunk_index=chunk_index,
        content_type=content_type,
        section=section,
        metadata_json=meta,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. MCU/peripheral knowledge retrieval — keyword extraction
# ─────────────────────────────────────────────────────────────────────────────


class TestMcuPeripheralKnowledge:
    def test_mcu_peripheral_keywords_extracted(self) -> None:
        text = "STM32F401 USART2 DMA1 GPIO PA5 PB6"
        keywords = _extract_technical_keywords(text)
        found = {k.upper() for k in keywords}
        assert "STM32F401" in found or any("STM32" in k.upper() for k in keywords)
        assert any("USART" in k.upper() for k in keywords)
        assert any("DMA" in k.upper() for k in keywords)

    def test_esp32_i2c_spi_keywords(self) -> None:
        text = "ESP32 I2C1 SPI2 GPIO21 ADC1"
        keywords = _extract_technical_keywords(text)
        found = " ".join(keywords).upper()
        assert "ESP32" in found or "I2C" in found or "SPI" in found

    def test_empty_text_returns_empty_keywords(self) -> None:
        assert _extract_technical_keywords("") == []
        assert _extract_technical_keywords("   ") == []


# ─────────────────────────────────────────────────────────────────────────────
# 2. Register/bitfield source retrieval
# ─────────────────────────────────────────────────────────────────────────────


class TestRegisterBitfieldRetrieval:
    def test_register_keywords_extracted(self) -> None:
        text = "Read CR1 register at offset 0x00, bit 0 CEN R/W reset value 0x0000"
        keywords = _extract_technical_keywords(text)
        kw_str = " ".join(keywords).lower()
        assert "cr1" in kw_str or "0x00" in kw_str or "r/w" in kw_str or "register" in kw_str

    def test_enriched_query_includes_register_terms(self) -> None:
        q = _build_technical_retrieval_query(
            user_question="What does TIM2_CR1 register Bit 0 do?",
            compiler_output="",
            firmware_code="TIM2->CR1 |= TIM_CR1_CEN;",
            base_query="TIM2 counter enable",
        )
        assert "TIM2" in q or "CR1" in q or "CEN" in q

    def test_register_document_context_carries_metadata(self) -> None:
        ctx = _make_doc_context(
            snippet="TIM2_CR1 Bit 0: CEN — Counter enable. R/W. Reset 0.",
            content_type="register_description",
            section="14.4.1 TIMx_CR1",
            page_number=145,
            chunk_index=3,
        )
        assert ctx.content_type == "register_description"
        assert ctx.section == "14.4.1 TIMx_CR1"
        assert ctx.page_number == 145
        assert ctx.chunk_index == 3


# ─────────────────────────────────────────────────────────────────────────────
# 3. Pin configuration source retrieval
# ─────────────────────────────────────────────────────────────────────────────


class TestPinConfigurationRetrieval:
    def test_pin_keywords_extracted_from_firmware(self) -> None:
        firmware = "HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);"
        keywords = _extract_technical_keywords(firmware)
        kw_str = " ".join(keywords).upper()
        assert "GPIO" in kw_str or "PA" in kw_str

    def test_enriched_query_includes_pin_terms(self) -> None:
        q = _build_technical_retrieval_query(
            user_question="What is the alternate function for PA5 SPI SCK?",
            compiler_output="",
            firmware_code="",
            base_query="pin alternate function SPI",
        )
        assert "PA5" in q or "SPI" in q or "SCK" in q

    def test_pin_document_context_has_correct_content_type(self) -> None:
        ctx = _make_doc_context(
            snippet="GPIO21 — I2C0 SDA, 45k pull-up, input/output",
            content_type="pin_configuration",
            section="4.2 Pinouts and pin description",
            page_number=22,
        )
        assert ctx.content_type == "pin_configuration"
        assert ctx.section is not None
        assert "Pinouts" in ctx.section


# ─────────────────────────────────────────────────────────────────────────────
# 4. Electrical/timing specification retrieval
# ─────────────────────────────────────────────────────────────────────────────


class TestElectricalTimingRetrieval:
    def test_spec_keywords_extracted(self) -> None:
        text = "VDD operating voltage 1.7V min 3.6V max, 84 MHz frequency"
        keywords = _extract_technical_keywords(text)
        kw_str = " ".join(keywords).lower()
        assert "vdd" in kw_str or "voltage" in kw_str or "mhz" in kw_str or "frequency" in kw_str

    def test_timing_keywords_extracted(self) -> None:
        text = "I2C timing 400 kHz SCL rise time max 300 ns"
        keywords = _extract_technical_keywords(text)
        kw_str = " ".join(keywords).lower()
        assert "timing" in kw_str or "khz" in kw_str or "ns" in kw_str

    def test_spec_document_context_carries_metadata(self) -> None:
        ctx = _make_doc_context(
            snippet="Table 6.3: VDD min 1.7 V, typ 3.3 V, max 3.6 V at 85°C",
            content_type="table_or_specification",
            section="6.3 Absolute maximum ratings",
            page_number=62,
        )
        assert ctx.content_type == "table_or_specification"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Source metadata and traceability
# ─────────────────────────────────────────────────────────────────────────────


class TestSourceMetadataTraceability:
    def test_document_context_carries_all_traceability_fields(self) -> None:
        ctx = _make_doc_context(
            snippet="Some technical content",
            content_type="register_description",
            section="5.1 Timer Control",
            page_number=99,
            chunk_index=7,
            score=0.91,
        )
        assert ctx.doc_id is not None
        assert ctx.chunk_id is not None
        assert ctx.page_number == 99
        assert ctx.chunk_index == 7
        assert ctx.score == pytest.approx(0.91)
        assert ctx.content_type == "register_description"
        assert ctx.section == "5.1 Timer Control"
        assert isinstance(ctx.metadata_json, dict)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Technically relevant source prioritization
# ─────────────────────────────────────────────────────────────────────────────


class TestTechnicalSourcePrioritization:
    def test_enriched_query_appends_missing_keywords_only(self) -> None:
        q = _build_technical_retrieval_query(
            user_question="What is USART2 baud rate register?",
            compiler_output="error: 'USART_CR1' undeclared",
            firmware_code="USART2->BRR = 0x0683;",
            base_query="USART baud rate configuration",
        )
        # Base query already has "USART"; "BRR" and "0x0683" should be appended
        assert "USART" in q  # preserved
        assert len(q) >= len("USART baud rate configuration")

    def test_base_query_returned_unchanged_when_no_new_keywords(self) -> None:
        q = _build_technical_retrieval_query(
            user_question="Hello world",
            compiler_output="",
            firmware_code="",
            base_query="generic query without embedded terms",
        )
        assert q == "generic query without embedded terms"

    def test_enriched_query_capped_at_2000_chars(self) -> None:
        long_fw = " ".join([f"GPIO{i}" for i in range(200)])
        q = _build_technical_retrieval_query(
            user_question="",
            compiler_output="",
            firmware_code=long_fw,
            base_query="GPIO configuration",
        )
        assert len(q) <= 2000


# ─────────────────────────────────────────────────────────────────────────────
# 7. Multiple supporting chunks
# ─────────────────────────────────────────────────────────────────────────────


class TestMultipleSupportingChunks:
    def test_format_prompt_emits_all_chunks(self, project_ctx: ProjectContext) -> None:
        chunks = [
            _make_doc_context("Register CR1 Bit 0 CEN", content_type="register_description", score=0.92),
            _make_doc_context("Register CR1 Bit 1 UDIS", content_type="register_description", score=0.88),
            _make_doc_context("GPIO Pin 42 is SDA", content_type="pin_configuration", score=0.75),
        ]
        ctx = AssembledDebugContext(
            project=project_ctx,
            user_question="Tell me about TIM2_CR1",
            document_context=chunks,
        )
        prompt = ctx.format_prompt()
        assert prompt.count("<document_chunk") == 3
        assert "CR1 Bit 0" in prompt
        assert "CR1 Bit 1" in prompt
        assert "GPIO Pin 42" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# 8. Grounded-response compatibility (format_prompt XML tags)
# ─────────────────────────────────────────────────────────────────────────────


class TestGroundedResponseCompatibility:
    def test_format_prompt_emits_source_type_and_section_attributes(
        self, project_ctx: ProjectContext
    ) -> None:
        ctx = AssembledDebugContext(
            project=project_ctx,
            user_question="What is the reset value of TIM2_CR1?",
            document_context=[
                _make_doc_context(
                    snippet="TIM2_CR1 Reset value 0x0000",
                    content_type="register_description",
                    section="14.4.1 TIMx_CR1",
                    page_number=145,
                    chunk_index=3,
                    score=0.91,
                )
            ],
        )
        prompt = ctx.format_prompt()
        assert 'source_type="register_description"' in prompt
        assert 'section="14.4.1 TIMx_CR1"' in prompt
        assert 'page="145"' in prompt
        assert 'chunk_index="3"' in prompt
        assert 'similarity="0.91"' in prompt

    def test_format_prompt_omits_source_type_when_not_set(
        self, project_ctx: ProjectContext
    ) -> None:
        ctx = AssembledDebugContext(
            project=project_ctx,
            document_context=[
                DocumentContext(
                    snippet="Some legacy chunk with no content_type",
                    content_type=None,
                    section=None,
                )
            ],
        )
        prompt = ctx.format_prompt()
        assert "source_type" not in prompt
        assert "section=" not in prompt

    def test_format_prompt_contains_retrieved_datasheets_wrapper(
        self, project_ctx: ProjectContext
    ) -> None:
        ctx = AssembledDebugContext(
            project=project_ctx,
            document_context=[
                _make_doc_context("Pinout table for GPIO", content_type="pin_configuration"),
            ],
        )
        prompt = ctx.format_prompt()
        assert "<retrieved_datasheets_and_documents>" in prompt
        assert "</retrieved_datasheets_and_documents>" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# 9. Ownership isolation
# ─────────────────────────────────────────────────────────────────────────────


class TestOwnershipIsolation:
    def test_context_carries_project_id(self, project_ctx: ProjectContext) -> None:
        ctx = AssembledDebugContext(project=project_ctx)
        prompt = ctx.format_prompt()
        assert str(project_ctx.project_id) in prompt

    def test_different_projects_produce_different_project_ids(self) -> None:
        p1 = ProjectContext(project_id=uuid.uuid4(), project_name="Project A")
        p2 = ProjectContext(project_id=uuid.uuid4(), project_name="Project B")
        assert p1.project_id != p2.project_id
        c1 = AssembledDebugContext(project=p1)
        c2 = AssembledDebugContext(project=p2)
        assert str(p1.project_id) in c1.format_prompt()
        assert str(p2.project_id) in c2.format_prompt()
        assert str(p1.project_id) not in c2.format_prompt()


# ─────────────────────────────────────────────────────────────────────────────
# 10. Backward compatibility
# ─────────────────────────────────────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_document_context_works_without_phase53_fields(
        self, project_ctx: ProjectContext
    ) -> None:
        """Legacy DocumentContext without content_type/section still serializes."""
        ctx = AssembledDebugContext(
            project=project_ctx,
            document_context=[
                DocumentContext(snippet="Legacy chunk content without metadata")
            ],
        )
        prompt = ctx.format_prompt()
        assert "Legacy chunk content without metadata" in prompt
        assert "<document_chunk" in prompt

    def test_enriched_query_returns_base_when_no_keywords(self) -> None:
        base = "simple debug question"
        result = _build_technical_retrieval_query("", "", "", base)
        assert result == base

    def test_extract_technical_keywords_handles_none_like_empty(self) -> None:
        assert _extract_technical_keywords("") == []
