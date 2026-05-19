"""``WaveletPacketDecomposer`` — full wavelet-packet tree decomposition.

Algorithm:
    1. Receive the input signal frame, wavelet_name, and level_count.
    2. Validate wavelet_name (non-empty string) and level_count (positive integer).
    3. Recursively apply the two-channel filter bank to BOTH the approximation AND
       detail subbands at each level (unlike the standard DWT which only splits the
       approximation subband).
    4. Produce 2^level_count leaf nodes, each containing coefficients for one subband.
    5. Return a WaveletFrame with 2^level_count subbands.

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
import pywt

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.types.wavelet_payload import WaveletPayload


def _run_wp(data: np.ndarray, wavelet_name: str, level: int) -> list[np.ndarray]:
    wp = pywt.WaveletPacket(data, wavelet_name, maxlevel=level)
    return [node.data for node in wp.get_level(level, "freq")]


class WaveletPacketDecomposer(Knot):
    """Wavelet-packet decomposition (binary subband tree)."""

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
        """Decompose the signal into the full wavelet-packet binary subband tree.

        Args:
            signal: Signal payload to decompose.
            wavelet_name: Name of the wavelet (non-empty string).
            level_count: Decomposition tree depth (positive integer).

        Returns:
            WaveletPayload of wavelet-packet leaf node coefficient arrays.

        Raises:
            ValueError: If wavelet_name or level_count are invalid.
        """
        if not isinstance(wavelet_name, str) or not wavelet_name:
            raise ValueError("WaveletPacketDecomposer: wavelet_name must be a non-empty string")
        if not isinstance(level_count, int) or level_count <= 0:
            raise ValueError("WaveletPacketDecomposer: level_count must be a positive integer")
        nodes = await asyncio.to_thread(_run_wp, signal.data, wavelet_name, level_count)
        frame = WaveletFrame(
            signal_id=signal.frame.signal_id,
            wavelet_name=wavelet_name,
            scale_count=len(nodes),
        )
        return WaveletPayload(metadata=frame, data=nodes)
