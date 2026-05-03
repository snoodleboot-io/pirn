"""``ESPRITEstimator`` — rotational-invariance subspace frequency estimator."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ESPRITEstimator(Knot):
    """ESPRIT high-resolution sinusoid estimator.

    Production needs a subspace eigen-decomposition implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        signal_subspace_dim: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(signal_subspace_dim, int) or signal_subspace_dim <= 0:
            raise ValueError(
                "ESPRITEstimator: signal_subspace_dim must be a positive integer"
            )
        self._signal_subspace_dim = signal_subspace_dim
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def signal_subspace_dim(self) -> int:
        return self._signal_subspace_dim

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        """Estimate sinusoid frequencies from the signal via ESPRIT and return a parameter mapping.

        Args:
            signal: Signal to estimate frequencies from using the rotational-invariance subspace method.

        Returns:
            Mapping containing ``signal_id``, ``signal_subspace_dim``, and ``estimator``.
        """
        return {
            "signal_id": signal.signal_id,
            "signal_subspace_dim": self._signal_subspace_dim,
            "estimator": "esprit",
        }
