"""``ConfidenceRouter`` — route based on numeric confidence score.

A :class:`Knot` that compares a numeric confidence score against a
threshold and returns a routing decision string: ``"primary"`` when the
score is at or above the threshold and ``"fallback"`` when below.

Algorithm:
    1. Receive the resolved ``score`` and ``threshold`` floats at process time.
    2. Validate that both values are numeric; raise on bad types.
    3. Compare ``float(score)`` against ``float(threshold)``.
    4. Return ``"primary"`` if score >= threshold, otherwise ``"fallback"``.

Math:
    decision = "primary"  if score >= threshold
               "fallback" otherwise

References:
    - pirn-native routing pattern; no external algorithm reference.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ConfidenceRouter(Knot):
    """Return routing decision based on confidence score vs threshold."""

    def __init__(
        self,
        *,
        score: Knot | float,
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(score=score, threshold=threshold, _config=_config, **kwargs)

    async def process(
        self,
        score: float,
        threshold: float,
        **_: Any,
    ) -> str:
        """Return 'primary' if score >= threshold, else 'fallback'.

        Args:
            score: The numeric confidence score to evaluate.
            threshold: The threshold to compare the score against.

        Returns:
            'primary' if score is at or above threshold, 'fallback' otherwise.

        Raises:
            TypeError: If score or threshold is not numeric.
        """
        if not isinstance(score, (int, float)):
            raise TypeError(
                "ConfidenceRouter: score must be a float, "
                f"got {type(score).__name__}"
            )
        if not isinstance(threshold, (int, float)):
            raise TypeError(
                "ConfidenceRouter: threshold must be a float, "
                f"got {type(threshold).__name__}"
            )
        if float(score) >= float(threshold):
            return "primary"
        return "fallback"
