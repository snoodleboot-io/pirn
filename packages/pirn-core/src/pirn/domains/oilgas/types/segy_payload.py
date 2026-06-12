"""``SegyPayload`` — SEG-Y volume metadata bundled with its trace sample buffer.

``volume`` carries the lineage metadata (volume_id, inline/xline/sample counts).
``data`` is a float32 array of shape ``(total_traces, sample_count)`` containing
the actual seismic trace amplitudes.  Both fields travel together through the
transport layer so downstream seismic knots receive the full volume in one input.
"""

from __future__ import annotations

import numpy as np

from pirn.core.payload import Payload
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class SegyPayload(Payload[SegyVolume, np.ndarray]):
    """SEG-Y seismic volume: metadata + trace sample buffer."""

    @property
    def volume(self) -> SegyVolume:
        return self._metadata

    @property
    def traces(self) -> np.ndarray:
        return self._data
