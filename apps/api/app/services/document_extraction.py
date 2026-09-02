from __future__ import annotations

import io
import logging
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.schemas.document import DocumentExtractionResult

logger = logging.getLogger(__name__)


class DocumentExtractionError(Exception):
    """Exception raised when document text extraction fails."""
    pass


class DocumentExtractionService:
    """Service responsible for extracting text and metadata from PDF datasheets / documentation."""

    @staticmethod
    def extract_pdf_content(pdf_bytes: bytes) -> DocumentExtractionResult:
        """Extract text, page count, and document metadata from raw PDF bytes.

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
                    page_text = page.extract_text() or ""
                    extracted_page_texts.append(page_text.strip())
                except Exception as page_err:
                    logger.warning("Error extracting text from page %d: %s", i + 1, page_err)
                    extracted_page_texts.append(f"[Page {i + 1} extraction failed: {page_err}]")

            full_text = "\n\n".join(t for t in extracted_page_texts if t).strip()

            # Extract basic PDF metadata if available
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
