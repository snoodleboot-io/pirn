"""Exponential importance x recency decay — the shared scoring primitive.

Both the :class:`~pirn_agents.memory_management.decay_scorer.DecayScorer` knot and
the :class:`~pirn_agents.memory_management.low_value_eviction_policy.LowValueEvictionPolicy`
score a memory's current value the same way, so the math lives in one pure
function. Value combines caller-assigned importance with a half-life recency
decay:

.. math::

    \\text{value} = \\text{importance} \\cdot 2^{-\\,\\text{age} / \\text{half\\_life}}

A record at age zero keeps its full importance; after one half-life its value
halves, and so on. Negative ages (a recency anchor in the future, e.g. clock
skew) are clamped to zero so value never exceeds importance.
"""

from __future__ import annotations


def decay_score(importance: float, age_seconds: float, half_life_seconds: float) -> float:
    """Return the half-life-decayed value of a memory.

    Args:
        importance: The record's importance in ``[0, 1]``.
        age_seconds: Seconds elapsed since the record's recency anchor; negative
            values are clamped to ``0``.
        half_life_seconds: The decay half-life in seconds; must be positive.

    Returns:
        ``importance * 2 ** (-age / half_life)`` with age floored at ``0``.

    Raises:
        ValueError: If ``half_life_seconds`` is not positive.
    """
    if half_life_seconds <= 0:
        raise ValueError(
            f"decay_score: half_life_seconds must be positive, got {half_life_seconds!r}"
        )
    age = max(0.0, float(age_seconds))
    return float(importance) * (2.0 ** (-age / float(half_life_seconds)))
