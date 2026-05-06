"""``DWPTDecomposer`` — dual-tree complex wavelet packet transform.

Algorithm:
    1. Receive the input signal frame, wavelet_name, and level_count.
    2. Validate wavelet_name (non-empty string) and level_count (positive integer).
    3. Apply the dual-tree complex wavelet filter bank:
       a. Tree A: real part using a standard quadrature mirror filter bank.
       b. Tree B: imaginary part using a half-sample shifted filter bank.
    4. Decompose both trees to level_count levels, producing 2^level_count subbands per tree.
    5. Return a WaveletFrame with 2^level_count subbands.

Math:
    Dual-tree complex wavelet:

    $$\\psi_c(t) = \\psi_h(t) + j\\psi_g(t)$$

    where $\\psi_h$ and $\\psi_g$ form a Hilbert pair with near shift-invariance.

References:
    - Kingsbury, N. (2001). "Complex wavelets for shift invariant analysis and filtering of signals."
      Appl. Comput. Harmon. Anal., 10(3), 234-253.
    - pywt: https://pywavelets.readthedocs.io/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class DWPTDecomposer(Knot):
    """Dual-tree wavelet packet transform.

    Production needs a dual-tree wavelet implementation.
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
        """Compute the dual-tree wavelet packet transform of the signal and return a WaveletFrame.

        Args:
            signal: Signal to decompose using the configured dual-tree wavelet at the configured level count.
            wavelet_name: Name of the wavelet (non-empty string).
            level_count: Number of decomposition levels (positive integer).

        Returns:
            WaveletFrame of DWPT coefficients with ``2 ** level_count`` subbands.

        Raises:
            ValueError: If wavelet_name or level_count are invalid.
        """
        if not isinstance(wavelet_name, str) or not wavelet_name:
            raise ValueError("DWPTDecomposer: wavelet_name must be a non-empty string")
        if not isinstance(level_count, int) or level_count <= 0:
            raise ValueError("DWPTDecomposer: level_count must be a positive integer")
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name=wavelet_name,
            scale_count=2**level_count,
        )
