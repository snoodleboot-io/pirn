"""``VMDDecomposer`` — variational mode decomposition."""

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
        mode_count: int,
        bandwidth_constraint: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(mode_count, int) or mode_count <= 0:
            raise ValueError(
                "VMDDecomposer: mode_count must be a positive integer"
            )
        if (
            not isinstance(bandwidth_constraint, (int, float))
            or bandwidth_constraint <= 0
        ):
            raise ValueError(
                "VMDDecomposer: bandwidth_constraint must be positive"
            )
        self._mode_count = mode_count
        self._bandwidth_constraint = float(bandwidth_constraint)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def mode_count(self) -> int:
        return self._mode_count

    @property
    def bandwidth_constraint(self) -> float:
        return self._bandwidth_constraint

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> WaveletFrame:
        return WaveletFrame(
            signal_id=signal.signal_id,
            wavelet_name="vmd",
            scale_count=self._mode_count,
        )
