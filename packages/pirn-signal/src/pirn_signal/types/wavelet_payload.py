"""``WaveletPayload`` — wavelet-domain signal metadata bundled with its coefficient arrays.

Returned by knots that produce wavelet decompositions (DWT, CWT, EMD, VMD, etc.).
``frame`` carries the wavelet name and scale count; ``data`` is a list of
coefficient arrays, one per decomposition level or mode.  For DWT the list
follows the pywt convention: ``[cA_n, cD_n, ..., cD_1]``.  For CWT and EMD
it is ``[scale_0, scale_1, ..., scale_K]``.
"""

from __future__ import annotations

import numpy as np
from pirn.core.payload import Payload

from pirn_signal.types.wavelet_frame import WaveletFrame


class WaveletPayload(Payload[WaveletFrame, list[np.ndarray]]):
    """Wavelet-domain signal: metadata frame + list of coefficient arrays."""

    @property
    def frame(self) -> WaveletFrame:
        return self._metadata
