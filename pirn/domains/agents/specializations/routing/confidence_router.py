"""``ConfidenceRouter`` — route based on numeric confidence score.

A :class:`Knot` that compares a numeric confidence score against a
threshold and returns a routing decision string: ``"primary"`` when the
score is at or above the threshold and ``"fallback"`` when below.
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
        threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(threshold, (int, float)):
            raise TypeError(
                "ConfidenceRouter: threshold must be a float, "
                f"got {type(threshold).__name__}"
            )
        self._threshold = float(threshold)
        super().__init__(score=score, _config=_config, **kwargs)

    async def process(
        self,
        score: float,
        **_: Any,
    ) -> str:
        """Return 'primary' if score >= threshold, else 'fallback'.

        Args:
            score: The numeric confidence score to evaluate.

        Returns:
            'primary' if score is at or above threshold, 'fallback' otherwise.

        Raises:
            TypeError: If score is not numeric.
        """
        if not isinstance(score, (int, float)):
            raise TypeError(
                "ConfidenceRouter: score must be a float, "
                f"got {type(score).__name__}"
            )
        if float(score) >= self._threshold:
            return "primary"
        return "fallback"
