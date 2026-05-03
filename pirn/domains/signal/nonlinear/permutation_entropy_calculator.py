"""``PermutationEntropyCalculator`` — ordinal pattern complexity measure."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PermutationEntropyCalculator(Knot):
    """Compute permutation entropy and normalised permutation entropy.

    Production needs ``antropy`` or a hand-rolled ordinal-pattern
    implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        order: int,
        delay: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(order, int) or order < 2 or order > 8:
            raise ValueError(
                "PermutationEntropyCalculator: order must be an integer in [2, 8]"
            )
        if not isinstance(delay, int) or delay <= 0:
            raise ValueError(
                "PermutationEntropyCalculator: delay must be a positive integer"
            )
        self._order = order
        self._delay = delay
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def order(self) -> int:
        return self._order

    @property
    def delay(self) -> int:
        return self._delay

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> dict[str, float]:
        """Compute permutation entropy from ordinal patterns in the signal.

        Args:
            signal: Time series signal to analyse.

        Returns:
            Dictionary with keys ``permutation_entropy`` and
            ``normalized_entropy``.
        """
        return {
            "permutation_entropy": 0.0,
            "normalized_entropy": 0.0,
        }
