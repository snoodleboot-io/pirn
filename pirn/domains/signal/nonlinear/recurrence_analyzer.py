"""``RecurrenceAnalyzer`` — recurrence-quantification analysis (RQA)."""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class RecurrenceAnalyzer(Knot):
    """Recurrence quantification analysis.

    Production needs ``pyrqa`` or a custom implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        embedding_dim: int,
        time_delay: int,
        recurrence_threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError(
                "RecurrenceAnalyzer: embedding_dim must be a positive integer"
            )
        if not isinstance(time_delay, int) or time_delay <= 0:
            raise ValueError(
                "RecurrenceAnalyzer: time_delay must be a positive integer"
            )
        if (
            not isinstance(recurrence_threshold, (int, float))
            or recurrence_threshold <= 0
        ):
            raise ValueError(
                "RecurrenceAnalyzer: recurrence_threshold must be positive"
            )
        self._embedding_dim = embedding_dim
        self._time_delay = time_delay
        self._recurrence_threshold = float(recurrence_threshold)
        super().__init__(signal=signal, _config=_config, **kwargs)

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    @property
    def time_delay(self) -> int:
        return self._time_delay

    @property
    def recurrence_threshold(self) -> float:
        return self._recurrence_threshold

    async def process(
        self, signal: SignalFrame, **_: Any
    ) -> Mapping[str, Any]:
        """Run recurrence quantification analysis on the signal and return a parameter mapping.

        Args:
            signal: Time series signal to analyse with recurrence quantification.

        Returns:
            Mapping containing ``signal_id``, ``embedding_dim``, ``time_delay``, and ``recurrence_threshold``.
        """
        return {
            "signal_id": signal.signal_id,
            "embedding_dim": self._embedding_dim,
            "time_delay": self._time_delay,
            "recurrence_threshold": self._recurrence_threshold,
        }
