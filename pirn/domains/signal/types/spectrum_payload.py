"""``SpectrumPayload`` — frequency-domain signal metadata bundled with its spectral array.

Returned by knots that produce frequency-domain representations (FFT, STFT,
PSD estimators, etc.).  ``frame`` carries bin count and frequency resolution;
``data`` is the spectral array, typically complex-valued, shaped
``(channels, bins)`` or ``(bins,)`` for single-channel results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame


@dataclass
class SpectrumPayload(PirnOpaqueValue):
    """Frequency-domain signal: metadata frame + spectral array."""

    frame: SpectrumFrame
    data: np.ndarray

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            **self.frame._pirn_audit_dict(),
            "data_shape": list(self.data.shape),
            "data_dtype": str(self.data.dtype),
        }
