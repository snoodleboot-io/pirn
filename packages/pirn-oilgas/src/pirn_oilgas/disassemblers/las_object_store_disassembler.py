"""``LasObjectStoreDisassembler`` — serialize a :class:`LASPayload` to raw LAS bytes.

Sits between upstream domain knots that produce
:class:`~pirn_oilgas.types.las_payload.LASPayload` and a downstream
connector sink knot (e.g. an object-store write sink) that consumes raw ``bytes``.
Performs no I/O.

Algorithm:
    1. Receive a :class:`LASPayload` from an upstream knot.
    2. Validate type and non-emptiness of curve data.
    3. On a thread, build a ``lasio.LASFile``, populate header items and curves
       from ``payload.las`` and ``payload.curve_data``, write to
       ``io.StringIO`` and encode the result to UTF-8 bytes.
    4. Return the raw LAS bytes.

References:
    - LAS 2.0 File Format Standard (1992), Canadian Well Logging Society.
    - LAS 3.0 File Format Standard (2001), Canadian Well Logging Society.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

import lasio
import numpy as np
from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_oilgas.types.las_payload import LASPayload


def _encode(payload: LASPayload) -> bytes:
    las = lasio.LASFile()

    las.well["WELL"].value = payload.las.well_id
    las.well["DEPT"].unit = payload.las.depth_unit

    curve_data = payload.curve_data
    mnemonics = list(curve_data.keys())

    depth_array: np.ndarray = curve_data.get("DEPT", curve_data.get("DEPTH", np.array([])))
    if depth_array.size == 0:
        first_mnemonic = mnemonics[0]
        depth_array = np.arange(len(curve_data[first_mnemonic]), dtype=np.float64)

    las.append_curve("DEPT", depth_array, unit=payload.las.depth_unit)

    for mnemonic, values in curve_data.items():
        if mnemonic in ("DEPT", "DEPTH"):
            continue
        las.append_curve(mnemonic, values)

    buf = io.StringIO()
    las.write(buf)
    return buf.getvalue().encode("utf-8")


class LasObjectStoreDisassembler(Disassembler):
    """Serialize a :class:`LASPayload` to raw LAS bytes.

    Receives a typed :class:`LASPayload` from an upstream domain knot and
    encodes the curve data into LAS 2.0 format bytes suitable for a connector
    sink. Performs no I/O.
    """

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
        payload: LASPayload,
        **_: Any,
    ) -> bytes:
        """Encode a :class:`LASPayload` into raw LAS bytes.

        Args:
            payload: The LAS payload to serialize.

        Returns:
            Raw UTF-8 encoded LAS 2.0 bytes representing the well-log data.

        Raises:
            TypeError: If ``payload`` is not a :class:`LASPayload`.
            ValueError: If ``payload.curve_data`` is empty.
        """
        if not isinstance(payload, LASPayload):
            raise TypeError(
                f"LasObjectStoreDisassembler: payload must be LASPayload, got {type(payload).__name__}"
            )
        if len(payload.curve_data) == 0:
            raise ValueError("LasObjectStoreDisassembler: payload.curve_data must be non-empty")
        return await asyncio.to_thread(_encode, payload)
