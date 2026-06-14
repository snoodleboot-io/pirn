"""``SpectrumPayload`` — frequency-domain signal metadata bundled with its spectral array.

Returned by knots that produce frequency-domain representations (FFT, STFT,
PSD estimators, etc.).  ``frame`` carries bin count and frequency resolution;
``data`` is the spectral array, typically complex-valued, shaped
``(channels, bins)`` or ``(bins,)`` for single-channel results.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_signal.types.spectrum_frame import SpectrumFrame


class SpectrumPayload(Payload[SpectrumFrame, np.ndarray]):
    """Frequency-domain signal: metadata frame + spectral array."""

    @property
    def frame(self) -> SpectrumFrame:
        return self._metadata
