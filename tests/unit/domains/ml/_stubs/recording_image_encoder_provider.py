"""Recording stub :class:`ImageEncoderProvider` for tests."""

from __future__ import annotations

from typing import Sequence

from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider


class RecordingImageEncoderProvider(ImageEncoderProvider):
    def __init__(self) -> None:
        self.calls: list[tuple[list[bytes], str | None]] = []
        self.closed: bool = False

    async def encode(
        self, images: Sequence[bytes], *, model: str | None = None
    ) -> list[list[float]]:
        self.calls.append((list(images), model))
        return [[0.4, 0.5, 0.6] for _ in images]

    async def close(self) -> None:
        self.closed = True
