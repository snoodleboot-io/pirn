"""``PronyEstimator`` — fit damped sinusoids via Prony's method."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PronyEstimator(Knot):
    """Estimate damped exponential modes via Prony's method.

    Production needs a Prony implementation on top of ``numpy``.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        component_count: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(component_count, int) or component_count <= 0:
            raise ValueError(
                "PronyEstimator: component_count must be a positive integer"
            )
        self._component_count = component_count
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def component_count(self) -> int:
        return self._component_count

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        """Fit damped sinusoidal modes to the signal via Prony's method and return a parameter mapping.

        Args:
            signal: Signal to decompose into damped exponential modes.

        Returns:
            Mapping containing ``signal_id``, ``component_count``, and ``estimator``.
        """
        return {
            "signal_id": signal.signal_id,
            "component_count": self._component_count,
            "estimator": "prony",
        }
