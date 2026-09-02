"""Embedding service abstraction and Gemini implementation.

Uses the google-genai SDK:
    client.models.embed_content(model="gemini-embedding-001", contents=...)
    -> EmbedContentResponse with .embeddings[i].values (list[float], dim 3072)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

try:
    from google import genai  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class BaseEmbeddingService(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Return an embedding vector for a single text string."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for a batch of text strings."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the expected embedding dimension."""

    @abstractmethod
    def model_name(self) -> str:
        """Return the embedding model identifier."""


class GeminiEmbeddingService(BaseEmbeddingService):
    """Gemini embedding provider using google-genai SDK."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = self._settings.embedding_model
        self._dim = self._settings.embedding_dimension

        if not self._settings.gemini_api_key:
            raise EmbeddingError("GEMINI_API_KEY is required for GeminiEmbeddingService")

        if genai is None:
            raise EmbeddingError("google-genai package is not installed")

        self._client = genai.Client(api_key=self._settings.gemini_api_key)

    def model_name(self) -> str:
        return self._model

    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        try:
            response = self._client.models.embed_content(
                model=self._model,
                contents=text,
            )
            values = response.embeddings[0].values
            if len(values) != self._dim:
                raise EmbeddingError(
                    f"Unexpected dimension {len(values)}, expected {self._dim}"
                )
            return list(values)
        except EmbeddingError:
            raise
        except Exception as e:
            logger.error("Embedding generation failed: %s", e)
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        The Gemini API supports passing a list of contents and returns one
        embedding per item.
        """
        if not texts:
            return []
        try:
            response = self._client.models.embed_content(
                model=self._model,
                contents=texts,
            )
            results: list[list[float]] = []
            for emb in response.embeddings:
                values = list(emb.values)
                if len(values) != self._dim:
                    raise EmbeddingError(
                        f"Unexpected dimension {len(values)}, expected {self._dim}"
                    )
                results.append(values)
            if len(results) != len(texts):
                raise EmbeddingError(
                    f"Expected {len(texts)} embeddings, got {len(results)}"
                )
            return results
        except EmbeddingError:
            raise
        except Exception as e:
            logger.error("Batch embedding failed: %s", e)
            raise EmbeddingError(f"Failed to generate batch embeddings: {e}") from e


def get_embedding_service(settings: Settings | None = None) -> BaseEmbeddingService:
    """Factory: return the configured embedding service instance."""
    s = settings or get_settings()
    if s.embedding_provider == "gemini":
        return GeminiEmbeddingService(s)
    raise ValueError(f"Unsupported embedding provider: {s.embedding_provider}")
