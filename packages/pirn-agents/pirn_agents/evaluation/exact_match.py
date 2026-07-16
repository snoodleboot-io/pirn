"""``exact_match`` — normalised string-equality metric."""

from __future__ import annotations

from pirn_agents.evaluation.metric_result import MetricResult
from pirn_agents.evaluation.text_normalization import normalize_text


def exact_match(prediction: str, reference: str, *, normalize: bool = True) -> MetricResult:
    """Score 1.0 when ``prediction`` equals ``reference``, else 0.0.

    With ``normalize`` (the default) both sides pass through
    :func:`~pirn_agents.evaluation.text_normalization.normalize_text`, so case
    and surrounding/collapsed whitespace do not cause a spurious mismatch. Two
    empty strings match (score 1.0); an empty prediction against a non-empty
    reference does not.

    Args:
        prediction: The produced output string.
        reference: The gold reference string.
        normalize: Apply case/whitespace normalisation before comparing.

    Returns:
        A :class:`MetricResult` named ``"exact_match"`` with score ``1.0``/``0.0``
        and the compared (post-normalisation) strings in ``detail``.

    Raises:
        TypeError: If either argument is not a ``str``.
    """
    if not isinstance(prediction, str):
        raise TypeError(f"exact_match: prediction must be a str, got {type(prediction).__name__}")
    if not isinstance(reference, str):
        raise TypeError(f"exact_match: reference must be a str, got {type(reference).__name__}")
    left = normalize_text(prediction) if normalize else prediction
    right = normalize_text(reference) if normalize else reference
    matched = left == right
    return MetricResult(
        name="exact_match",
        score=1.0 if matched else 0.0,
        detail={"prediction": left, "reference": right, "normalized": normalize},
    )
