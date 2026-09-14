"""``DWPTDecomposer`` — discrete wavelet packet transform (full binary subband tree).

Algorithm:
    1. Receive the input signal frame, wavelet_name, and level_count.
    2. Validate wavelet_name (non-empty string) and level_count (positive integer).
    3. Recursively apply the two-channel filter bank to BOTH the approximation AND
       detail subbands at each level (unlike the standard DWT, which only splits the
       approximation subband).
    4. Collect the 2^level_count leaf nodes at depth level_count in frequency order.
    5. Return a WaveletPayload with one coefficient array per leaf subband.

Math:
    Wavelet packet subband at node $(j, n)$:

    $$W_{j,n,k} = \\sum_m h^{(n)}[m - 2k] W_{j-1, \\lfloor n/2 \\rfloor, m}$$

    where $h^{(n)}$ alternates between low-pass and high-pass filters.

References:
    - Coifman, R.R. & Wickerhauser, M.V. (1992). "Entropy-based algorithms for best basis selection."
      IEEE Trans. Inf. Theory, 38(2), 713-718.
    - pywt.WaveletPacket: https://pywavelets.readthedocs.io/en/latest/ref/wavelet-packets.html
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_signal.bindings.py_wavelets_binding import PyWaveletsBinding
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.wavelet_frame import WaveletFrame
from pirn_signal.types.wavelet_payload import WaveletPayload


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
        nodes = await asyncio.to_thread(
            DWPTDecomposer._run_dwpt, signal.data, wavelet_name, level_count
        )
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name=wavelet_name,
            scale_count=len(nodes),
        )
        return WaveletPayload(metadata=frame, data=nodes)

    @staticmethod
    def _run_dwpt(
        data: np.ndarray, wavelet_name: str, level: int
    ) -> list[NDArray[np.floating[Any]]]:
        pywt = PyWaveletsBinding.load()
        return pywt.wavelet_packet_level(data, wavelet_name, level)
