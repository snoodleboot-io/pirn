"""``WsiObjectStoreDisassembler`` — disassemble a :class:`WSITilePayload` into bytes.

Sits between domain knots that produce :class:`~pirn.domains.health.types.wsi_tile_payload.WSITilePayload`
and an object store sink connector that expects raw ``bytes``.

Algorithm:
    1. Receive a :class:`WSITilePayload`.
    2. Validate the payload type.
    3. On a thread, convert ``payload.pixels`` (a numpy RGB array) to PNG bytes via Pillow.
    4. Return the resulting ``bytes``.

References:
    - Pillow: https://pillow.readthedocs.io/
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

import numpy as np
from PIL import Image

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.types.wsi_tile_payload import WSITilePayload


def _to_png_bytes(payload: WSITilePayload) -> bytes:
    img = Image.fromarray(payload.pixels.astype(np.uint8), mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class WsiObjectStoreDisassembler(Disassembler):
    """Disassemble a :class:`WSITilePayload` into PNG bytes for object store upload."""

    def __init__(
        self,
        *,
        payload: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, _config=_config, **kwargs)

    async def process(
        self,
        payload: WSITilePayload,
        **_: Any,
    ) -> bytes:
        """Convert the WSI tile pixel array to PNG bytes.

        Args:
            payload: :class:`WSITilePayload` produced by an upstream pathology knot.

        Returns:
            PNG-encoded ``bytes`` of the tile's RGB pixel array.

        Raises:
            TypeError: If ``payload`` is not a :class:`WSITilePayload`.
        """
        if not isinstance(payload, WSITilePayload):
            raise TypeError(
                f"WsiObjectStoreDisassembler: payload must be WSITilePayload, "
                f"got {type(payload).__name__}"
            )
        return await asyncio.to_thread(_to_png_bytes, payload)
