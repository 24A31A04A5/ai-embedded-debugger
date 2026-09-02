"""Document chunking service — splits extracted text into deterministic, page-aware chunks."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas.document import RawChunk

logger = logging.getLogger(__name__)

# Regex for common technical datasheet section/table/register headings
HEADING_REGEX = re.compile(
    r"^(?:"
    r"(?:Section|Chapter|Appendix)\s+\d+(?:\.\d+)*[\.:]?\s+[^\n]+"
    r"|\d+(?:\.\d+)+\s+[A-Za-z][^\n]+"
    r"|[A-Za-z0-9_]{2,}\s*[-–—]\s*.+"
    r"|Table\s+\d+(?:[-\.]\d+)*[\.:]?\s+[^\n]+"
    r")$",
    re.MULTILINE,
)




def classify_technical_content(text: str) -> dict[str, Any]:
    """Detect presence of register maps, tables, pinouts, and technical specs."""
    meta: dict[str, Any] = {}

    has_register = bool(
        re.search(
            r"\b(?:Register|Bit[s]?\s+\d+|R/W|Reset\s+value|0x[0-9A-Fa-f]{2,})\b",
            text,
            re.IGNORECASE,
        )
    )
    has_table = bool(
        "|" in text
        or "\t" in text
        or bool(re.search(r"\b(?:Table\s+\d+|Min\s+Typ\s+Max|VIL|VIH|VDD|VSS|Symbol\s+Parameter)\b", text))
    )
    has_pinout = bool(
        re.search(
            r"\b(?:GPIO\d+|Pin\s+\d+|Pinout|SDA|SCL|MOSI|MISO|SCK|TXD|RXD|PWM|ADC\d+)\b",
            text,
            re.IGNORECASE,
        )
    )

    if has_register:
        meta["has_register"] = True
    if has_table:
        meta["has_table"] = True
    if has_pinout:
        meta["has_pinout"] = True

    if has_register:
        meta["content_type"] = "register_description"
    elif has_table:
        meta["content_type"] = "table_or_specification"
    elif has_pinout:
        meta["content_type"] = "pin_configuration"
    else:
        meta["content_type"] = "text"

    return meta


class DocumentChunkingService:
    """Split document text into fixed-size, overlap-aware chunks with technical structure tracking.

    Features:
    - Configurable chunk_size and chunk_overlap.
    - Structure-aware splitting on paragraph / section boundaries.
    - Section and heading extraction with metadata tagging.
    - Content-type classification (registers, tables, pinouts, specifications).
    - Preserves deterministic ordering (chunk_index) and 1-indexed page boundaries.
    - Safely handles empty, plain, or partially structured documents.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be >= 0 and < chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_text(self, text: str, page_texts: list[str] | None = None) -> list[RawChunk]:
        """Chunk *text* into a list of ``RawChunk`` objects.

        If *page_texts* is supplied (one entry per page), each chunk will
        carry the 1-indexed page number of its origin.  Otherwise
        ``page_number`` will be ``None``.
        """
        if not text or not text.strip():
            return []

        # Build a mapping from character offset → page number
        page_map: list[tuple[int, int]] | None = None
        if page_texts:
            page_map = self._build_page_offset_map(page_texts)

        # Step 1: split into paragraph-level segments
        segments = self._paragraph_split(text)
        if not segments:
            return []

        # Step 2: merge segments into chunks of ≤ chunk_size with overlap and metadata
        chunks = self._merge_segments_into_chunks(segments, text, page_map)
        return chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _paragraph_split(text: str) -> list[str]:
        """Split text on double-newlines (paragraph boundaries).

        Falls back to single-newline splits, then sentence splits, if paragraphs
        are too large.
        """
        paragraphs = re.split(r"\n\s*\n", text)
        result: list[str] = []
        for para in paragraphs:
            stripped = para.strip()
            if stripped:
                result.append(stripped)
        return result

    @staticmethod
    def _sentence_split(text: str) -> list[str]:
        """Best-effort sentence tokenisation (regex-based)."""
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]

    def _merge_segments_into_chunks(
        self,
        segments: list[str],
        full_text: str,
        page_map: list[tuple[int, int]] | None,
    ) -> list[RawChunk]:
        """Greedily merge paragraph segments into chunks respecting size limits and tracking sections."""
        chunks: list[RawChunk] = []
        current_parts: list[str] = []
        current_len = 0
        chunk_index = 0
        active_section: str | None = None

        def _flush() -> None:
            nonlocal chunk_index, current_parts, current_len
            if not current_parts:
                return
            chunk_text = "\n\n".join(current_parts)
            page_num = self._page_for_chunk(chunk_text, full_text, page_map)

            meta = classify_technical_content(chunk_text)
            if active_section:
                meta["section"] = active_section

            chunks.append(
                RawChunk(
                    chunk_index=chunk_index,
                    content=chunk_text,
                    page_number=page_num,
                    metadata=meta,
                )
            )
            chunk_index += 1

            # Overlap: keep trailing parts whose combined length ≤ overlap
            if self.chunk_overlap > 0:
                overlap_parts: list[str] = []
                overlap_len = 0
                for part in reversed(current_parts):
                    if overlap_len + len(part) > self.chunk_overlap:
                        break
                    overlap_parts.insert(0, part)
                    overlap_len += len(part)
                current_parts = overlap_parts
                current_len = overlap_len
            else:
                current_parts = []
                current_len = 0

        for segment in segments:
            # Check if segment starts with a section heading
            first_line = segment.split("\n")[0].strip()
            if HEADING_REGEX.match(first_line):
                active_section = first_line

            # If a single segment exceeds chunk_size, sub-split it
            if len(segment) > self.chunk_size:
                _flush()
                sub_chunks = self._split_large_segment(segment)
                for sub in sub_chunks:
                    if current_len + len(sub) > self.chunk_size and current_parts:
                        _flush()
                    current_parts.append(sub)
                    current_len += len(sub)
                continue

            # Normal case: try to append segment to current chunk
            separator_len = 2 if current_parts else 0  # "\n\n"
            if current_len + len(segment) + separator_len > self.chunk_size and current_parts:
                _flush()

            current_parts.append(segment)
            current_len += len(segment) + (2 if len(current_parts) > 1 else 0)

        _flush()
        return chunks



    def _split_large_segment(self, segment: str) -> list[str]:
        """Break an oversized segment into sentence-level pieces, then
        further split any sentence longer than chunk_size at word boundaries.
        """
        sentences = self._sentence_split(segment)
        result: list[str] = []
        for sentence in sentences:
            if len(sentence) <= self.chunk_size:
                result.append(sentence)
            else:
                # Word-boundary split
                words = sentence.split()
                buf: list[str] = []
                buf_len = 0
                for word in words:
                    needed = len(word) + (1 if buf else 0)
                    if buf_len + needed > self.chunk_size and buf:
                        result.append(" ".join(buf))
                        buf = []
                        buf_len = 0
                    buf.append(word)
                    buf_len += needed
                if buf:
                    result.append(" ".join(buf))
        return result

    # ------------------------------------------------------------------
    # Page tracking
    # ------------------------------------------------------------------

    @staticmethod
    def _build_page_offset_map(page_texts: list[str]) -> list[tuple[int, int]]:
        """Return a list of (start_offset, page_number) from page_texts.

        We reconstruct the offset positions that correspond to the full_text
        built by joining non-empty page texts with ``\\n\\n``.
        """
        offset = 0
        mapping: list[tuple[int, int]] = []
        first = True
        for idx, pt in enumerate(page_texts):
            stripped = pt.strip()
            if not stripped:
                continue
            if not first:
                offset += 2  # for "\n\n" separator
            mapping.append((offset, idx + 1))  # 1-indexed page number
            offset += len(stripped)
            first = False
        return mapping

    @staticmethod
    def _page_for_chunk(
        chunk_text: str,
        full_text: str,
        page_map: list[tuple[int, int]] | None,
    ) -> int | None:
        """Determine the page number for a chunk by locating it in full_text."""
        if not page_map:
            return None
        pos = full_text.find(chunk_text[:200])  # first 200 chars is enough
        if pos == -1:
            return None
        # Find the page whose offset is ≤ pos
        page_num = None
        for start_offset, pnum in page_map:
            if start_offset <= pos:
                page_num = pnum
            else:
                break
        return page_num
