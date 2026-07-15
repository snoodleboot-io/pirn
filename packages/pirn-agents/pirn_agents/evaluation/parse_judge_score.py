"""``parse_judge_score`` — read a normalised 0..1 score from judge free text."""

from __future__ import annotations

import re

_FIRST_NUMBER = re.compile(r"[-+]?\d*\.?\d+")


def parse_judge_score(text: str) -> float:
    """Extract the first number from ``text`` as a score clamped to ``[0, 1]``.

    Lenient and provider-neutral: it reads the first numeric token in the
    judge's reply. A value already in ``[0, 1]`` is used directly; a value in
    ``(1, 10]`` is treated as a 0-10 rating and divided by 10; anything larger is
    clamped to ``1.0`` and a negative to ``0.0``. Replies with no number score
    ``0.0`` (fail closed).

    Args:
        text: The judge's reply text.

    Returns:
        A score in ``[0.0, 1.0]``.

    Raises:
        TypeError: If ``text`` is not a ``str``.
    """
    if not isinstance(text, str):
        raise TypeError(f"parse_judge_score: text must be a str, got {type(text).__name__}")
    match = _FIRST_NUMBER.search(text)
    if match is None:
        return 0.0
    value = float(match.group())
    if value > 10.0:
        return 1.0
    if value > 1.0:
        value = value / 10.0
    return max(0.0, min(1.0, value))
