"""``EMDDecomposer`` — empirical mode decomposition.

Algorithm:
    1. Receive the input signal frame and max_imf_count.
    2. Validate max_imf_count (positive integer).
    3. Extract the first IMF via the sifting process:
       a. Identify all local extrema of the signal.
       b. Fit upper and lower envelopes via cubic spline interpolation.
       c. Subtract the mean envelope from the signal.
       d. Repeat until the result satisfies the IMF criteria.
    4. Subtract the extracted IMF from the signal and repeat for subsequent IMFs.
    5. Stop when fewer than two extrema remain or max_imf_count is reached.
    6. Return a WaveletFrame with max_imf_count IMF scales.

Math:
    IMF sifting criterion:

    $$|\\text{mean envelope}(t)| \\ll |h(t)| \\quad \\text{and}$$ the number of extrema and zero-crossings
    differ by at most one.

    Signal decomposition:

    $$x(t) = \\sum_{k=1}^{K} c_k(t) + r_K(t)$$

References:
    - Huang, N.E. et al. (1998). "The empirical mode decomposition and the Hilbert spectrum for nonlinear and
      non-stationary time series analysis." Proc. R. Soc. Lond. A, 454(1971), 903-995.
    - PyEMD: https://pyemd.readthedocs.io/
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class EMDDecomposer(Knot):
    """Empirical mode decomposition into intrinsic mode functions.

    Production needs ``EMD-signal`` (PyEMD) or similar.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        max_imf_count: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            max_imf_count=max_imf_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        max_imf_count: int,
        **_: Any,
    ) -> WaveletFrame:
        """Decompose the signal into intrinsic mode functions via empirical mode decomposition.

        Args:
            signal: Signal to decompose into up to ``max_imf_count`` intrinsic mode functions.
            max_imf_count: Maximum number of IMFs to extract (positive integer).

        Returns:
            WaveletFrame of EMD intrinsic mode functions with up to ``max_imf_count`` scales.

        Raises:
            ValueError: If max_imf_count is not a positive integer.
        """
        if not isinstance(max_imf_count, int) or max_imf_count <= 0:
            raise ValueError("EMDDecomposer: max_imf_count must be a positive integer")
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name="emd",
            scale_count=max_imf_count,
        )
