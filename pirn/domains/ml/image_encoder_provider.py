"""Interface for image-encoder providers.

Concrete implementations (CLIP, ResNet via remote API, ...) inherit
from :class:`ImageEncoderProvider` and override every method.
Pirn treats providers as opaque (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`).
"""

from __future__ import annotations

from typing import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class ImageEncoderProvider(PirnOpaqueValue):
    """Interface every image-encoder implementation must satisfy."""

    async def encode(
        self, images: Sequence[bytes], *, model: str | None = None
    ) -> list[list[float]]:
        """Return one embedding vector per image, in input order."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement encode()"
        )

    async def close(self) -> None:
        """Close the provider and release any underlying resources."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement close()"
        )

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the provider."""
        self._config = None
