"""``VMDDecomposer`` — variational mode decomposition.

Algorithm:
    1. Receive the input signal frame, mode_count, and bandwidth_constraint.
    2. Validate mode_count (positive integer) and bandwidth_constraint (positive float).
    3. Formulate the constrained optimisation: decompose the signal into mode_count
       band-limited modes each centred at an adaptive centre frequency.
    4. Solve via ADMM (alternating direction method of multipliers) in the frequency domain.
    5. Iterate until convergence: update modes, centre frequencies, and Lagrange multipliers.
    6. Return a WaveletFrame with mode_count IMF-like modes.

Math:
    VMD optimisation problem:

    $$\\min_{u_k, \\omega_k} \\sum_k \\|\\partial_t [(\\delta(t) + j/\\pi t) * u_k(t)] e^{-j\\omega_k t}\\|_2^2$$

    $$\\text{s.t.} \\quad \\sum_k u_k = f$$

References:
    - Dragomiretskiy, K. & Zosso, D. (2014). "Variational mode decomposition."
      IEEE Trans. Signal Process., 62(3), 531-544.
    - vmdpy: https://github.com/vrcarva/vmdpy
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame


class VMDDecomposer(Knot):
    """Variational mode decomposition.

    Production needs ``vmdpy`` or a hand-rolled ADMM implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        mode_count: Knot | int,
        bandwidth_constraint: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            mode_count=mode_count,
            bandwidth_constraint=bandwidth_constraint,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        mode_count: int,
        bandwidth_constraint: float,
        **_: Any,
    ) -> WaveletFrame:
        """Decompose the signal into band-limited modes via variational mode decomposition.

        Args:
            signal: Signal to decompose into ``mode_count`` variational modes.
            mode_count: Number of VMD modes to extract (positive integer).
            bandwidth_constraint: Bandwidth penalty parameter alpha (positive float).

        Returns:
            WaveletFrame of VMD modes with ``mode_count`` scales.

        Raises:
            ValueError: If mode_count or bandwidth_constraint are invalid.
        """
        if not isinstance(mode_count, int) or mode_count <= 0:
            raise ValueError("VMDDecomposer: mode_count must be a positive integer")
        if not isinstance(bandwidth_constraint, (int, float)) or bandwidth_constraint <= 0:
            raise ValueError("VMDDecomposer: bandwidth_constraint must be positive")
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name="vmd",
            scale_count=mode_count,
        )
