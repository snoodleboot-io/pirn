"""``LASPayload`` — LAS well-log metadata bundled with its curve data arrays.

``las`` carries the lineage metadata (well_id, curve mnemonics, depth unit).
``data`` maps each curve mnemonic to a depth-indexed float64 array.
Both fields travel together through the transport layer so downstream
petrophysics knots receive the full curve buffers in one input.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_oilgas.types.las_file import LASFile


class LASPayload(Payload[LASFile, dict[str, np.ndarray]]):
    """LAS well-log: metadata + curve data arrays."""

    @property
    def las(self) -> LASFile:
        return self._metadata

    @property
    def curve_data(self) -> dict[str, np.ndarray]:
        return self._data
