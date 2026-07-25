"""``ExactMatch`` — normalised string-equality metric."""

from __future__ import annotations

from typing import Any

from pirn_agents.evaluation.metric import Metric
from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.text_normalizer import TextNormalizer


class ExactMatch(Metric):
    """Score 1.0 when the prediction equals the reference, else 0.0.

    With ``normalize`` (the default) both sides pass through
    :class:`~pirn_agents.evaluation.text_normalizer.TextNormalizer`, so case and
    surrounding/collapsed whitespace do not cause a spurious mismatch. Two empty
    strings match (score 1.0); an empty prediction against a non-empty reference
    does not.
    """

    def __init__(self, *, normalize: bool = True) -> None:
        """Configure whether comparison applies case/whitespace normalisation.

        Args:
            normalize: Apply case/whitespace normalisation before comparing.
        """
        self._normalize = normalize
        self._normalizer = TextNormalizer()

    @property
    def name(self) -> str:
        """The metric's stable identifier."""
        return "exact_match"

    def score(self, actual: Any, expected: Any = None) -> MetricResult:
        """Score ``actual`` (the prediction) against ``expected`` (the reference).

        Args:
            actual: The produced output string.
            expected: The gold reference string.

        Returns:
            A :class:`MetricResult` named ``"exact_match"`` with score
            ``1.0``/``0.0`` and the compared (post-normalisation) strings in
            ``detail``.

        Raises:
            TypeError: If either argument is not a ``str``.
        """
        if not isinstance(actual, str):
            raise TypeError(f"ExactMatch: prediction must be a str, got {type(actual).__name__}")
        if not isinstance(expected, str):
            raise TypeError(f"ExactMatch: reference must be a str, got {type(expected).__name__}")
        left = self._normalizer.normalize(actual) if self._normalize else actual
        right = self._normalizer.normalize(expected) if self._normalize else expected
        matched = left == right
        return MetricResult(
            name="exact_match",
            score=1.0 if matched else 0.0,
            detail={"prediction": left, "reference": right, "normalized": self._normalize},
        )
