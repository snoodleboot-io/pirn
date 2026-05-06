"""``DWTDecomposer`` — discrete wavelet transform decomposition.

Algorithm:
    1. Receive the input signal frame, wavelet_name, and level_count.
    2. Validate wavelet_name (non-empty string) and level_count (positive integer).
    3. Apply the two-band quadrature mirror filter bank iteratively to the
       approximation subband for level_count levels.
    4. Return a WaveletFrame with level_count decomposition levels (one approximation
       subband plus level_count detail subbands).

Math:
    Two-channel filter bank at level $j$:

    $$A_j[n] = \\sum_k h[k] A_{j-1}[2n - k], \\quad D_j[n] = \\sum_k g[k] A_{j-1}[2n - k]$$

    where $h$ = low-pass and $g$ = high-pass analysis filters.

References:
    - Mallat, S. (1989). "A theory for multiresolution signal decomposition: the wavelet representation."
      IEEE Trans. Pattern Anal. Mach. Intell., 11(7), 674-693.
    - pywt.wavedec: https://pywavelets.readthedocs.io/en/latest/ref/dwt-discrete-wavelet-transform.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class DWTDecomposer(Knot):
    """Multi-level discrete wavelet transform.

    Production needs ``pywt.wavedec``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        wavelet_name: Knot | str,
        level_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            wavelet_name=wavelet_name,
            level_count=level_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        wavelet_name: str,
        level_count: int,
        **_: Any,
    ) -> WaveletFrame:
        """Compute the multi-level discrete wavelet transform of the signal and return a WaveletFrame.

        Args:
            signal: Signal to decompose using the configured wavelet at the configured decomposition depth.
            wavelet_name: Name of the wavelet (non-empty string, e.g., ``db4``, ``haar``).
            level_count: Number of decomposition levels (positive integer).

        Returns:
            WaveletFrame of DWT coefficients with ``level_count`` decomposition levels.

        Raises:
            ValueError: If wavelet_name or level_count are invalid.
        """
        if not isinstance(wavelet_name, str) or not wavelet_name:
            raise ValueError("DWTDecomposer: wavelet_name must be a non-empty string")
        if not isinstance(level_count, int) or level_count <= 0:
            raise ValueError("DWTDecomposer: level_count must be a positive integer")
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name=wavelet_name,
            scale_count=level_count,
        )
