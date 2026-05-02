"""``MUSICEstimator`` — high-resolution sinusoid frequency estimation."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class MUSICEstimator(Knot):
    """MUltiple SIgnal Classification frequency estimator.

    Production needs an eigen-decomposition-based subspace estimator
    on top of ``numpy.linalg``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        signal_subspace_dim: int,
        frequency_grid_size: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal_subspace_dim, int) or signal_subspace_dim <= 0:
            raise ValueError(
                "MUSICEstimator: signal_subspace_dim must be a positive integer"
            )
        if not isinstance(frequency_grid_size, int) or frequency_grid_size <= 0:
            raise ValueError(
                "MUSICEstimator: frequency_grid_size must be a positive integer"
            )
        self._signal_subspace_dim = signal_subspace_dim
        self._frequency_grid_size = frequency_grid_size
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def signal_subspace_dim(self) -> int:
        return self._signal_subspace_dim

    @property
    def frequency_grid_size(self) -> int:
        return self._frequency_grid_size

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        return {
            "signal_id": signal.signal_id,
            "signal_subspace_dim": self._signal_subspace_dim,
            "frequency_grid_size": self._frequency_grid_size,
            "estimator": "music",
        }
