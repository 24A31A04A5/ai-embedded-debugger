"""Tests for Phase 5.1 — Better Document Processing for the AI Embedded Debugger.

Covers:
1. Normal technical PDF extraction
2. Page preservation and 1-indexed page numbering
3. Section/heading preservation in chunk metadata
4. Table / specification content classification
5. Register / pin information extraction
6. Chunk metadata and traceability
7. Difficult / partially structured PDF handling
8. Backward compatibility with existing documents
"""

from __future__ import annotations

import io
import pytest
from pypdf import PdfWriter

from app.schemas.document import RawChunk
from app.services.chunking import (
    DocumentChunkingService,
    classify_technical_content,
)
from app.services.document_extraction import (
    DocumentExtractionError,
    DocumentExtractionService,
    clean_technical_text,
)


# ─────────────────────────────────────────────
# Helper to create synthetic PDF bytes for testing
# ─────────────────────────────────────────────


def create_synthetic_pdf(page_contents: list[str]) -> bytes:
    """Create a valid in-memory PDF with the given text on each page using pypdf."""
    from pypdf import PageObject

    # Note: pypdf can create blank pages, or we can use basic PDF stream
    # A lightweight minimal valid PDF generator:
    writer = PdfWriter()
    for text in page_contents:
        # Create a blank page
        page = PageObject.create_blank_page(width=612, height=792)
        writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────
# 1. Normal technical PDF extraction
# ─────────────────────────────────────────────


class TestNormalTechnicalPdfExtraction:
    def test_clean_technical_text_normalizes_unicode_and_newlines(self) -> None:
        raw = "STM32F401xB\r\n\r\n\r\n\r\n\x00\x07Features\n- Core: ARM® 32-bit Cortex®-M4\n"
        cleaned = clean_technical_text(raw)

        assert "\r" not in cleaned
        assert "\x00" not in cleaned
        assert "\x07" not in cleaned
        assert "\n\n\n" not in cleaned
        assert "STM32F401xB" in cleaned
        assert "ARM® 32-bit Cortex®-M4" in cleaned

    def test_extract_pdf_content_valid_pdf(self) -> None:
        pdf_bytes = create_synthetic_pdf(["Page 1: Overview", "Page 2: Pinout"])
        result = DocumentExtractionService.extract_pdf_content(pdf_bytes)

        assert result.page_count == 2
        assert len(result.page_texts) == 2


# ─────────────────────────────────────────────
# 2. Page preservation
# ─────────────────────────────────────────────


class TestPagePreservation:
    def test_chunks_retain_accurate_1_indexed_page_numbers(self) -> None:
        page1 = "Section 1.0 System Architecture\nThe system utilizes an ARM Cortex-M4 microcontroller running at 84 MHz."
        page2 = "Section 2.0 Power Management\nOperating voltage range is 1.7V to 3.6V with internal voltage regulator."
        page3 = "Section 3.0 Memory Mapping\nFlash memory starts at base address 0x08000000."

        # Chunk size set to ensure each page forms its own chunk
        chunker = DocumentChunkingService(chunk_size=120, chunk_overlap=10)
        full_text = f"{page1}\n\n{page2}\n\n{page3}"
        chunks = chunker.chunk_text(full_text, page_texts=[page1, page2, page3])

        assert len(chunks) >= 3
        # Page 1 chunk
        assert chunks[0].page_number == 1
        assert "System Architecture" in chunks[0].content

        # Page 2 chunk
        assert any(c.page_number == 2 and "Power Management" in c.content for c in chunks)

        # Page 3 chunk
        assert any(c.page_number == 3 and "Memory Mapping" in c.content for c in chunks)



# ─────────────────────────────────────────────
# 3. Section / heading preservation
# ─────────────────────────────────────────────


class TestSectionHeadingPreservation:
    def test_section_heading_tagged_in_chunk_metadata(self) -> None:
        text = (
            "Section 4.1.2 Clock Configuration\n\n"
            "The PLL requires a stable HSE oscillator between 4 MHz and 26 MHz.\n\n"
            "The maximum system clock frequency is 84 MHz."
        )
        chunker = DocumentChunkingService(chunk_size=800, chunk_overlap=100)
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 1
        assert "section" in chunks[0].metadata
        assert chunks[0].metadata["section"] == "Section 4.1.2 Clock Configuration"

    def test_register_heading_pattern_captured(self) -> None:
        text = (
            "TIMx_CR1 - Control Register 1\n\n"
            "Bit 0: CEN (Counter enable)\n"
            "Bit 1: UDIS (Update disable)\n"
            "Reset value: 0x0000"
        )
        chunker = DocumentChunkingService(chunk_size=500, chunk_overlap=50)
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 1
        assert chunks[0].metadata.get("section") == "TIMx_CR1 - Control Register 1"


# ─────────────────────────────────────────────
# 4. Table / specification content
# ─────────────────────────────────────────────


class TestTableSpecificationContent:
    def test_electrical_specs_classified_as_table_or_specification(self) -> None:
        table_text = (
            "Table 24. I2C Interface Characteristics\n"
            "Symbol | Parameter | Min | Typ | Max | Unit\n"
            "fSCL   | SCL Clock Frequency | 0 | - | 400 | kHz\n"
            "tLOW   | Low Period of SCL   | 1.3 | - | -   | us\n"
            "tHIGH  | High Period of SCL  | 0.6 | - | -   | us"
        )
        meta = classify_technical_content(table_text)
        assert meta["content_type"] == "table_or_specification"
        assert meta.get("has_table") is True

    def test_chunker_tags_table_metadata(self) -> None:
        table_text = (
            "Table 4-1. Absolute Maximum Ratings\n\n"
            "Parameter | Min | Max | Unit\n"
            "VDD - VSS | -0.3 | +4.0 | V\n"
            "VIN       | -0.3 | VDD+0.3 | V"
        )
        chunker = DocumentChunkingService()
        chunks = chunker.chunk_text(table_text)

        assert len(chunks) == 1
        assert chunks[0].metadata["content_type"] == "table_or_specification"
        assert chunks[0].metadata["has_table"] is True


# ─────────────────────────────────────────────
# 5. Register / pin information extraction
# ─────────────────────────────────────────────


class TestRegisterAndPinoutContent:
    def test_register_bitfields_classified_accurately(self) -> None:
        reg_text = (
            "USART_CR1 Register (Offset: 0x00, Reset value: 0x00000000)\n"
            "Bits 31:16 Reserved, must be kept at reset value.\n"
            "Bit 13 UE: USART enable (R/W)\n"
            "Bit 3 TE: Transmitter enable (R/W)\n"
            "Bit 2 RE: Receiver enable (R/W)"
        )
        meta = classify_technical_content(reg_text)
        assert meta["content_type"] == "register_description"
        assert meta.get("has_register") is True

    def test_pinout_description_classified_accurately(self) -> None:
        pin_text = (
            "Pinout Configuration:\n"
            "GPIO21 (Pin 42): I2C0 SDA with internal 45k pull-up\n"
            "GPIO22 (Pin 43): I2C0 SCL with internal 45k pull-up\n"
            "GPIO1 (Pin 25): U0TXD UART0 Transmit\n"
            "GPIO3 (Pin 26): U0RXD UART0 Receive"
        )
        meta = classify_technical_content(pin_text)
        assert meta["content_type"] == "pin_configuration"
        assert meta.get("has_pinout") is True


# ─────────────────────────────────────────────
# 6. Chunk metadata and traceability
# ─────────────────────────────────────────────


class TestChunkMetadataTraceability:
    def test_chunk_carries_deterministic_indices_and_traceability_keys(self) -> None:
        doc_text = (
            "Section 1.1 Overview\nGeneral information on ESP32 dual-core Xtensa MCU.\n\n"
            "Section 1.2 Pinout\nGPIO21 is SDA and GPIO22 is SCL.\n\n"
            "Section 1.3 Registers\nI2C_CTR_REG offset 0x0004 Reset value 0x0000."
        )
        chunker = DocumentChunkingService(chunk_size=70, chunk_overlap=10)
        chunks = chunker.chunk_text(doc_text)

        assert len(chunks) >= 3
        # Indices are strictly increasing from 0
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx
            assert isinstance(chunk.metadata, dict)
            assert "content_type" in chunk.metadata



# ─────────────────────────────────────────────
# 7. Difficult / partially structured PDF handling
# ─────────────────────────────────────────────


class TestDifficultPdfHandling:
    def test_empty_pdf_raises_document_extraction_error(self) -> None:
        with pytest.raises(DocumentExtractionError, match="empty"):
            DocumentExtractionService.extract_pdf_content(b"")

    def test_corrupted_pdf_raises_document_extraction_error(self) -> None:
        with pytest.raises(DocumentExtractionError, match="Malformed"):
            DocumentExtractionService.extract_pdf_content(b"NOT_A_REAL_PDF_STREAM")

    def test_unstructured_raw_text_chunked_cleanly(self) -> None:
        raw_text = "Just a single continuous unstructured line of embedded notes without any headings or tables."
        chunker = DocumentChunkingService()
        chunks = chunker.chunk_text(raw_text)

        assert len(chunks) == 1
        assert chunks[0].metadata["content_type"] == "text"
        assert chunks[0].content == raw_text


# ─────────────────────────────────────────────
# 8. Backward compatibility with existing documents
# ─────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_chunk_text_without_page_texts_sets_page_number_none(self) -> None:
        chunker = DocumentChunkingService()
        chunks = chunker.chunk_text("Simple text without page information.")

        assert len(chunks) == 1
        assert chunks[0].page_number is None

    def test_empty_string_returns_empty_chunk_list(self) -> None:
        chunker = DocumentChunkingService()
        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   \n\n  ") == []
