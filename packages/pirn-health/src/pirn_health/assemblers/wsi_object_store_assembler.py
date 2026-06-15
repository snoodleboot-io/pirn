"""``WsiObjectStoreAssembler`` — assemble a :class:`WSITilePayload` from image bytes.

Sits between an object store connector (which produces ``bytes``) and downstream
domain knots that consume :class:`~pirn_health.types.wsi_tile_payload.WSITilePayload`.

Algorithm:
    1. Receive ``body`` (raw PNG/JPEG bytes), ``slide_id``, and ``tile_index``.
    2. Validate types and values.
    3. Decode the image bytes via ``PIL.Image.open`` on a thread and convert to an
       RGB numpy array of shape ``(height, width, 3)``.
    4. Build a :class:`WSITile` descriptor from the decoded image dimensions and return a
       :class:`WSITilePayload`.

References:
    - Goode, A., et al. (2013). OpenSlide: A vendor-neutral software foundation for
      digital pathology. JPI.
    - Pillow: https://pillow.readthedocs.io/
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

import numpy as np
from PIL import Image
from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.wsi_tile import WSITile
from pirn_health.types.wsi_tile_payload import WSITilePayload


def _assemble_tile(body: bytes, slide_id: str, tile_index: int) -> WSITilePayload:
    img = Image.open(io.BytesIO(body)).convert("RGB")
    pixels = np.array(img, dtype=np.uint8)
    height, width = pixels.shape[:2]
    tile = WSITile(
        slide_id=slide_id,
        tile_x=tile_index,
        tile_y=0,
        level=0,
        width=width,
        height=height,
    )
    return WSITilePayload(metadata=tile, data=pixels)


class WsiObjectStoreAssembler(Assembler):
    """Assemble a :class:`WSITilePayload` from raw image bytes stored in an object store."""

    def __init__(
        self,
        *,
        body: Knot,
        slide_id: Knot | str,
        tile_index: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            body=body,
            slide_id=slide_id,
            tile_index=tile_index,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        body: bytes,
        slide_id: str,
        tile_index: int,
        **_: Any,
    ) -> WSITilePayload:
        """Decode image bytes into a :class:`WSITilePayload`.

        Args:
            body: Raw PNG or JPEG bytes from an object store connector.
            slide_id: Non-empty slide identifier string.
            tile_index: Non-negative integer tile index within the slide.

        Returns:
            :class:`WSITilePayload` with an RGB pixel array of shape ``(height, width, 3)``
            and a :class:`WSITile` descriptor populated from the decoded image dimensions.

        Raises:
            TypeError: If ``body`` is not ``bytes``, ``slide_id`` is not a ``str``, or
                ``tile_index`` is not an ``int``.
            ValueError: If ``slide_id`` is empty or ``tile_index`` is negative.
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"WsiObjectStoreAssembler: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(slide_id, str):
            raise TypeError(
                f"WsiObjectStoreAssembler: slide_id must be str, got {type(slide_id).__name__}"
            )
        if not slide_id:
            raise ValueError("WsiObjectStoreAssembler: slide_id must be non-empty")
        if not isinstance(tile_index, int):
            raise TypeError(
                f"WsiObjectStoreAssembler: tile_index must be int, got {type(tile_index).__name__}"
            )
        if tile_index < 0:
            raise ValueError("WsiObjectStoreAssembler: tile_index must be >= 0")
        return await asyncio.to_thread(_assemble_tile, body, slide_id, tile_index)
