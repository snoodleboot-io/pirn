"""``WaveletPayload`` — wavelet-domain signal metadata bundled with its coefficient arrays.

Returned by knots that produce wavelet decompositions (DWT, CWT, EMD, VMD, etc.).
``frame`` carries the wavelet name and scale count; ``data`` is a list of
coefficient arrays, one per decomposition level or mode.  For DWT the list
follows the pywt convention: ``[cA_n, cD_n, ..., cD_1]``.  For CWT and EMD
it is ``[scale_0, scale_1, ..., scale_K]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


@dataclass
class WaveletPayload(PirnOpaqueValue):
    """Wavelet-domain signal: metadata frame + list of coefficient arrays."""

    frame: WaveletFrame
    data: list[np.ndarray]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            **self.frame._pirn_audit_dict(),
            "n_scales": len(self.data),
            "scale_shapes": [list(a.shape) for a in self.data],
        }
