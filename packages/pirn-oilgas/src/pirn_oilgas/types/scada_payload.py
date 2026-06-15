"""``ScadaPayload`` — SCADA sensor metadata bundled with its sample values.

``series`` carries the lineage metadata (sensor_id, sample_count,
sample_interval_sec).  ``data`` is a float64 array of shape
``(sample_count,)`` containing the actual sensor readings.  Both fields
travel together through the transport layer so downstream computation knots
receive the full time series in one input.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_oilgas.types.scada_time_series import ScadaTimeSeries


class ScadaPayload(Payload[ScadaTimeSeries, np.ndarray]):
    """SCADA sensor channel: metadata + sample values array."""

    @property
    def series(self) -> ScadaTimeSeries:
        return self._metadata

    @property
    def values(self) -> np.ndarray:
        return self._data
