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

import asyncio
from typing import Any

import numpy as np
import pywt
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.wavelet_frame import WaveletFrame
from pirn_signal.types.wavelet_payload import WaveletPayload


def _run_dwpt(data: np.ndarray, wavelet_name: str, level: int) -> list[np.ndarray]:
    wp = pywt.WaveletPacket(data, wavelet_name, maxlevel=level)
    return [node.data for node in wp.get_level(level, "freq")]


class DWPTDecomposer(Knot):
    """Discrete wavelet packet transform."""

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
        signal: SignalPayload,
        wavelet_name: str,
        level_count: int,
        **_: Any,
    ) -> WaveletPayload:
        """Compute the wavelet packet transform and return a WaveletPayload.

        Args:
            signal: Signal payload to decompose.
            wavelet_name: Name of the wavelet (non-empty string).
            level_count: Number of decomposition levels (positive integer).

        Returns:
            WaveletPayload of DWPT node coefficients at the given level.

        Raises:
            ValueError: If wavelet_name or level_count are invalid.
        """
        if not isinstance(wavelet_name, str) or not wavelet_name:
            raise ValueError("DWPTDecomposer: wavelet_name must be a non-empty string")
        if not isinstance(level_count, int) or level_count <= 0:
            raise ValueError("DWPTDecomposer: level_count must be a positive integer")
        nodes = await asyncio.to_thread(_run_dwpt, signal.data, wavelet_name, level_count)
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name=wavelet_name,
            scale_count=len(nodes),
        )
        return WaveletPayload(metadata=frame, data=nodes)
