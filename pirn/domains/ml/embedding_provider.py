"""Interface for text embedding providers.

Concrete implementations (OpenAI, Cohere, sentence-transformers, ...)
inherit from :class:`EmbeddingProvider` and override every method.
Pirn treats providers as opaque (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`).
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class EmbeddingProvider(PirnOpaqueValue):
    """Interface every text-embedding implementation must satisfy."""

    async def embed(
        self, texts: Sequence[str], *, model: str | None = None
    ) -> list[list[float]]:
        """Return one embedding vector per input string in input order."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement embed()"
        )

    async def close(self) -> None:
        """Close the provider and release any underlying resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the provider."""
        self._config = None
