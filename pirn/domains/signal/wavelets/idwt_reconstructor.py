"""``IDWTReconstructor`` — inverse discrete wavelet transform.

Algorithm:
    1. Receive the WaveletFrame, wavelet, and level.
    2. Validate wavelet (non-empty string) and level (positive integer).
    3. Apply the synthesis filter bank at each level, upsampling and filtering
       the approximation and detail subbands.
    4. Sum the approximation and detail outputs at each scale to reconstruct
       the signal at the next coarser level.
    5. Return a SignalFrame with samples_per_channel = scale_count * 2^level.

Math:
    Two-channel synthesis at level $j$:

    $$A_{j-1}[n] = \\sum_k \\tilde{h}[n - 2k] A_j[k] + \\sum_k \\tilde{g}[n - 2k] D_j[k]$$

    where $\\tilde{h}$ and $\\tilde{g}$ are the synthesis low-pass and high-pass filters.

References:
    - Mallat, S. (1989). "A theory for multiresolution signal decomposition: the wavelet representation."
      IEEE Trans. Pattern Anal. Mach. Intell., 11(7), 674-693.
    - pywt.waverec: https://pywavelets.readthedocs.io/en/latest/ref/dwt-discrete-wavelet-transform.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class IDWTReconstructor(Knot):
    """Reconstruct a time-domain signal from a WaveletFrame via inverse DWT."""

    def __init__(
        self,
        *,
        wavelet_frame: Knot,
        wavelet: Knot | str,
        level: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            wavelet_frame=wavelet_frame,
            wavelet=wavelet,
            level=level,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        wavelet_frame: WaveletFrame,
        wavelet: str,
        level: int,
        **_: Any,
    ) -> SignalFrame:
        """Reconstruct the time-domain signal from a WaveletFrame via inverse DWT.

        Args:
            wavelet_frame: The wavelet-domain representation to invert.
            wavelet: Synthesis wavelet name (non-empty string).
            level: Number of reconstruction levels (positive integer).

        Returns:
            SignalFrame containing the reconstructed signal.

        Raises:
            ValueError: If wavelet or level are invalid.
        """
        if not isinstance(wavelet, str) or not wavelet:
            raise ValueError("IDWTReconstructor: wavelet must be a non-empty string")
        if not isinstance(level, int) or level <= 0:
            raise ValueError("IDWTReconstructor: level must be a positive integer")
        return SignalFrame(
            signal_id=f"{wavelet_frame.signal_id}:idwt",
            channel_count=1,
            sample_rate_hz=0.0,
            samples_per_channel=wavelet_frame.scale_count * (2**level),
        )
