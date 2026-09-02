from __future__ import annotations

import io
import logging
import re
import unicodedata
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.schemas.document import DocumentExtractionResult

logger = logging.getLogger(__name__)


class DocumentExtractionError(Exception):
    """Exception raised when document text extraction fails."""
    pass


def clean_technical_text(text: str) -> str:
    """Clean common PDF extraction artifacts while preserving technical formatting.

    - Normalizes Unicode ligatures (ﬁ -> fi, ﬂ -> fl, etc.)
    - Removes non-printable control characters while preserving standard whitespace
    - Normalizes excessive blank lines while preserving paragraph and table structure
    """
    if not text:
        return ""

    # Normalize unicode (compatibility decomposition & composition)
    text = unicodedata.normalize("NFKC", text)

    # Replace null and non-printable control characters (except newline, carriage return, tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Normalize line endings to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Clean trailing whitespaces per line while preserving indentation
    lines = [line.rstrip() for line in text.split("\n")]

    # Normalize 3+ consecutive newlines into 2
    cleaned_text = "\n".join(lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    return cleaned_text.strip()


class DocumentExtractionService:
    """Service responsible for extracting text and metadata from PDF datasheets / documentation."""

    @staticmethod
    def extract_pdf_content(pdf_bytes: bytes) -> DocumentExtractionResult:
        """Extract text, page count, and document metadata from raw PDF bytes.

        Preserves page boundaries, technical tables, register blocks, and section headers.

        Raises:
            DocumentExtractionError: If the PDF is corrupted, empty, encrypted, or cannot be parsed.
        """
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise DocumentExtractionError("PDF file is empty")

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except Exception as e:
            logger.warning("Failed to initialize PDF reader: %s", e)
            raise DocumentExtractionError(f"Malformed or invalid PDF: {e}") from e

        try:
            if reader.is_encrypted:
                try:
                    # Attempt decrypt with empty password for standard open permissions
                    decrypt_success = reader.decrypt("")
                    if decrypt_success == 0:
                        raise DocumentExtractionError("PDF is password protected and cannot be extracted")
                except Exception as e:
                    raise DocumentExtractionError(f"Encrypted PDF cannot be read: {e}") from e

            page_count = len(reader.pages)
            if page_count == 0:
                raise DocumentExtractionError("PDF document contains 0 pages")

            extracted_page_texts: list[str] = []
            for i, page in enumerate(reader.pages):
                try:
                    # extract_text preserves layout-oriented text blocks
                    raw_page_text = page.extract_text() or ""
                    cleaned_page_text = clean_technical_text(raw_page_text)
                    extracted_page_texts.append(cleaned_page_text)
                except Exception as page_err:
                    logger.warning("Error extracting text from page %d: %s", i + 1, page_err)
                    extracted_page_texts.append(f"[Page {i + 1} extraction failed: {page_err}]")

            full_text = "\n\n".join(t for t in extracted_page_texts if t).strip()

            # Extract PDF metadata if available
            pdf_metadata: dict[str, Any] = {}
            if reader.metadata:
                for k, v in reader.metadata.items():
                    key_str = str(k).lstrip("/")
                    if v is not None:
                        pdf_metadata[key_str] = str(v)

            return DocumentExtractionResult(
                text=full_text,
                page_count=page_count,
                metadata=pdf_metadata,
                page_texts=extracted_page_texts,
            )

        except DocumentExtractionError:
            raise
        except (PyPdfError, Exception) as e:
            logger.warning("PDF extraction failed: %s", e)
            raise DocumentExtractionError(f"Failed to extract text from PDF: {e}") from e

