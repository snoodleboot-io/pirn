"""``SignalPayload`` — time-domain signal metadata bundled with its sample array.

Returned by knots that produce or transform time-domain signal data.
``frame`` carries the lineage metadata; ``data`` is the sample array,
shaped ``(channels, samples)`` for multi-channel signals or ``(samples,)``
for mono.  Both fields travel together through the transport layer so
downstream knots receive the full picture in one input.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_signal.types.signal_frame import SignalFrame


class SignalPayload(Payload[SignalFrame, np.ndarray]):
    """Time-domain signal: metadata frame + sample array."""

    @property
    def frame(self) -> SignalFrame:
        return self._metadata
