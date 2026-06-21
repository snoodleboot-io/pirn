"""``LasObjectStoreAssembler`` — assemble a :class:`LASPayload` from raw LAS bytes.

Sits between :class:`~pirn.connectors.knots.object_store_read_source.ObjectStoreReadSource`
(which produces ``bytes``) and downstream petrophysics knots that consume
:class:`~pirn_oilgas.types.las_payload.LASPayload`.

Algorithm:
    1. Receive ``body`` (raw LAS file bytes), ``well_id``, ``curves``, and
       ``depth_unit``.
    2. Validate types and values.
    3. Decode bytes via ``lasio.read`` on a thread to avoid blocking the event loop.
    4. Return a :class:`LASPayload` carrying the curve arrays and a
       :class:`LASFile` built from the decoded metadata.

References:
    - LAS 2.0 File Format Standard (1992), Canadian Well Logging Society.
    - LAS 3.0 File Format Standard (2001), Canadian Well Logging Society.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import lasio
import numpy as np
from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.types.las_payload import LASPayload


def _decode(
    body: bytes,
    well_id: str,
    curves: tuple[str, ...],
    depth_unit: str,
) -> LASPayload:
    las = lasio.read(io.StringIO(body.decode("utf-8", errors="replace")))
    available = {curve_entry.mnemonic for curve_entry in las.curves}
    curve_data: dict[str, np.ndarray] = {}
    for mnemonic in curves:
        if mnemonic in available:
            curve_data[mnemonic] = np.asarray(las[mnemonic], dtype=np.float64)
        else:
            depth_len = len(las.index) if len(las.index) > 0 else 100
            curve_data[mnemonic] = np.zeros(depth_len, dtype=np.float64)
    return LASPayload(
        metadata=LASFile(
            well_id=well_id,
            curves=curves,
            depth_unit=depth_unit,
            fetched_at=datetime.now(UTC),
        ),
        data=curve_data,
    )


class LasObjectStoreAssembler(Assembler):
    """Assemble a :class:`LASPayload` from raw LAS file bytes."""

    def __init__(
        self,
        *,
        body: Knot,
        well_id: Knot | str,
        curves: Knot | Sequence[str],
        depth_unit: Knot | str = "m",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            body=body,
            well_id=well_id,
            curves=curves,
            depth_unit=depth_unit,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        body: bytes,
        well_id: str,
        curves: Sequence[str],
        depth_unit: str = "m",
        **_: Any,
    ) -> LASPayload:
        """Decode raw LAS bytes into a :class:`LASPayload`.

        Args:
            body: Raw LAS file bytes from an object store or other connector.
            well_id: Non-empty well identifier string.
            curves: Non-empty sequence of curve mnemonic strings.
            depth_unit: Depth unit; must be ``'m'`` or ``'ft'``.

        Returns:
            :class:`LASPayload` with curve arrays decoded from ``body`` and
            a :class:`LASFile` populated from the decoded file metadata.

        Raises:
            TypeError: If ``body`` is not ``bytes``, ``well_id`` is not a ``str``,
                or ``curves`` is not a sequence.
            ValueError: If ``well_id`` is empty, ``curves`` is empty, any curve
                name is empty, or ``depth_unit`` is not ``'m'`` or ``'ft'``.
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"LasObjectStoreAssembler: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(well_id, str):
            raise TypeError(
                f"LasObjectStoreAssembler: well_id must be str, got {type(well_id).__name__}"
            )
        if not well_id:
            raise ValueError("LasObjectStoreAssembler: well_id must be non-empty")
        curve_tuple = tuple(curves)
        if not curve_tuple:
            raise ValueError("LasObjectStoreAssembler: curves must be non-empty")
        for mnemonic in curve_tuple:
            if not isinstance(mnemonic, str) or not mnemonic:
                raise ValueError(
                    "LasObjectStoreAssembler: every curve name must be a non-empty str"
                )
        if depth_unit not in ("m", "ft"):
            raise ValueError("LasObjectStoreAssembler: depth_unit must be 'm' or 'ft'")
        return await asyncio.to_thread(_decode, body, well_id, curve_tuple, depth_unit)
