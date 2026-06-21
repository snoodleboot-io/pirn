"""``HealthSignalPayload`` — multi-channel signal metadata bundled with its sample array.

Returned by EEG/MEG and wearable knots that produce or transform time-domain
signal data.  ``frame`` carries the lineage metadata; ``data`` is the sample
array shaped ``(channels, samples)`` for multi-channel signals or ``(samples,)``
for mono.  Both fields travel together through the transport layer so downstream
knots receive the full picture in one input.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_health.types.health_signal_frame import HealthSignalFrame


class HealthSignalPayload(Payload[HealthSignalFrame, np.ndarray]):
    """Time-domain signal: metadata frame + sample array."""

    @property
    def frame(self) -> HealthSignalFrame:
        return self._metadata
