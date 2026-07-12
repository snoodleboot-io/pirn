"""``AcceptGate`` — the scored accept gate for the Evaluator-Optimizer loop.

A :class:`Knot` that decides whether a :class:`JudgeVerdict` clears a threshold.
It is the scored generalisation of
:class:`~pirn_agents.control.reflection_check.ReflectionCheck`: where
``ReflectionCheck`` asks the LLM for a boolean "iterate again?", ``AcceptGate``
turns the judge's continuous score into the same accept/reject decision without
an extra LLM round-trip.

Algorithm:
    1. Receive a :class:`JudgeVerdict` and a numeric ``threshold``.
    2. Validate types at process time.
    3. Return ``True`` when ``verdict.score >= threshold``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.evaluator_optimizer.judge_verdict import JudgeVerdict


class AcceptGate(Knot):
    """Return whether a :class:`JudgeVerdict` meets the accept threshold."""

    def __init__(
        self,
        *,
        verdict: Knot | JudgeVerdict,
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(verdict=verdict, threshold=threshold, _config=_config, **kwargs)

    async def process(
        self,
        verdict: JudgeVerdict,
        threshold: float,
        **_: Any,
    ) -> bool:
        """Return ``True`` when ``verdict.score`` meets or exceeds ``threshold``.

        Args:
            verdict: The judge's scored verdict.
            threshold: The minimum score to accept.

        Returns:
            ``True`` if accepted, ``False`` otherwise.

        Raises:
            TypeError: If ``verdict`` is not a :class:`JudgeVerdict` or
                ``threshold`` is not numeric.
        """
        if not isinstance(verdict, JudgeVerdict):
            raise TypeError(
                f"AcceptGate: verdict must be a JudgeVerdict, got {type(verdict).__name__}"
            )
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            raise TypeError(
                f"AcceptGate: threshold must be numeric, got {type(threshold).__name__}"
            )
        return verdict.score >= float(threshold)
