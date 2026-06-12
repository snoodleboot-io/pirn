"""``SegyObjectStoreDisassembler`` — serialize a :class:`SegyPayload` to raw SEG-Y bytes.

Sits between upstream domain knots that produce
:class:`~pirn.domains.oilgas.types.segy_payload.SegyPayload` and a downstream
connector sink knot (e.g. an object-store write sink) that consumes raw ``bytes``.
Performs no I/O.

Algorithm:
    1. Receive a :class:`SegyPayload` from an upstream knot.
    2. Validate type and non-emptiness of the trace buffer.
    3. On a thread, write the traces to a temporary SEG-Y file via ``segyio``,
       then read the file back as raw bytes.
    4. Return the raw SEG-Y bytes.

References:
    - SEG Technical Standards Committee (2017). SEG-Y_r2.0 Data Exchange Format.
      Society of Exploration Geophysicists.
"""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any

import numpy as np

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.types.segy_payload import SegyPayload


def _encode(payload: SegyPayload) -> bytes:
    import segyio  # optional dependency

    traces: np.ndarray = payload.traces
    if traces.ndim == 1:
        traces = traces.reshape(1, -1)

    total_traces, sample_count = traces.shape

    with tempfile.NamedTemporaryFile(suffix=".segy", delete=False) as tmp:
        tmp_path = tmp.name

    spec = segyio.spec()
    spec.sorting = None
    spec.format = 1
    spec.samples = np.arange(sample_count, dtype=np.float32)
    spec.tracecount = total_traces

    with segyio.create(tmp_path, spec) as segy_file:
        segy_file.bin.update(tsort=segyio.TraceSortingFormat.UNKNOWN_SORTING)
        for idx in range(total_traces):
            segy_file.trace[idx] = traces[idx].astype(np.float32)

    with open(tmp_path, "rb") as raw:
        return raw.read()


class SegyObjectStoreDisassembler(Disassembler):
    """Serialize a :class:`SegyPayload` to raw SEG-Y bytes.

    Receives a typed :class:`SegyPayload` from an upstream domain knot and
    encodes the trace buffer into SEG-Y format bytes suitable for a connector
    sink. Performs no I/O beyond the temporary file used by ``segyio``.
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
        payload: SegyPayload,
        **_: Any,
    ) -> bytes:
        """Encode a :class:`SegyPayload` into raw SEG-Y bytes.

        Args:
            payload: The SEG-Y payload to serialize.

        Returns:
            Raw SEG-Y bytes encoding the seismic trace amplitudes.

        Raises:
            TypeError: If ``payload`` is not a :class:`SegyPayload`.
            ValueError: If ``payload.traces`` is empty.
        """
        if not isinstance(payload, SegyPayload):
            raise TypeError(
                f"SegyObjectStoreDisassembler: payload must be SegyPayload, got {type(payload).__name__}"
            )
        if payload.traces.size == 0:
            raise ValueError("SegyObjectStoreDisassembler: payload.traces must be non-empty")
        return await asyncio.to_thread(_encode, payload)
