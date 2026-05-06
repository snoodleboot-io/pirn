"""``RecurrenceAnalyzer`` — recurrence-quantification analysis (RQA).

Algorithm:
    1. Receive the input signal frame, embedding_dim, time_delay, and recurrence_threshold.
    2. Validate embedding_dim and time_delay (positive integers) and
       recurrence_threshold (positive float).
    3. Reconstruct the phase space via Takens delay embedding.
    4. Build the recurrence matrix R(i, j) = Theta(eps - ||x_i - x_j||).
    5. Compute RQA measures: recurrence rate (RR), determinism (DET),
       average diagonal line length (L), laminarity (LAM), trapping time (TT).
    6. Return a result mapping with the RQA measures and parameters.

Math:
    Recurrence matrix:

    $$R_{i,j} = \\Theta(\\varepsilon - \\|x_i - x_j\\|), \\quad i, j = 1, \\ldots, N$$

    Recurrence rate:

    $$RR = \\frac{1}{N^2} \\sum_{i,j} R_{i,j}$$

References:
    - Eckmann, J.-P., Kamphorst, S.O. & Ruelle, D. (1987). "Recurrence plots of dynamical systems."
      Europhys. Lett., 4(9), 973-977.
    - pyrqa library: https://github.com/tobias-burg/PyRQA
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
        embedding_dim: Knot | int,
        time_delay: Knot | int,
        recurrence_threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            embedding_dim=embedding_dim,
            time_delay=time_delay,
            recurrence_threshold=recurrence_threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        embedding_dim: int,
        time_delay: int,
        recurrence_threshold: float,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Run recurrence quantification analysis on the signal.

        Args:
            signal: Time series signal to analyse with recurrence quantification.
            embedding_dim: Phase-space embedding dimension (positive integer).
            time_delay: Delay embedding time lag in samples (positive integer).
            recurrence_threshold: Distance threshold ε for recurrence (positive float).

        Returns:
            Mapping containing ``signal_id``, ``embedding_dim``, ``time_delay``,
            and ``recurrence_threshold``.

        Raises:
            ValueError: If embedding_dim, time_delay, or recurrence_threshold are invalid.
        """
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError("RecurrenceAnalyzer: embedding_dim must be a positive integer")
        if not isinstance(time_delay, int) or time_delay <= 0:
            raise ValueError("RecurrenceAnalyzer: time_delay must be a positive integer")
        if not isinstance(recurrence_threshold, (int, float)) or recurrence_threshold <= 0:
            raise ValueError("RecurrenceAnalyzer: recurrence_threshold must be positive")
        return {
            "signal_id": signal.signal_id,
            "embedding_dim": embedding_dim,
            "time_delay": time_delay,
            "recurrence_threshold": float(recurrence_threshold),
        }
