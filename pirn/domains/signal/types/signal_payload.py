"""``SignalPayload`` — time-domain signal metadata bundled with its sample array.

Returned by knots that produce or transform time-domain signal data.
``frame`` carries the lineage metadata; ``data`` is the sample array,
shaped ``(channels, samples)`` for multi-channel signals or ``(samples,)``
for mono.  Both fields travel together through the transport layer so
downstream knots receive the full picture in one input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.signal.types.signal_frame import SignalFrame


@dataclass
class SignalPayload(PirnOpaqueValue):
    """Time-domain signal: metadata frame + sample array."""

    frame: SignalFrame
    data: np.ndarray

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            **self.frame._pirn_audit_dict(),
            "data_shape": list(self.data.shape),
            "data_dtype": str(self.data.dtype),
        }
