"""``_ShouldReflectCheck`` — should the reflector run this iteration?

The ``Check`` (core role, ``pirn.nodes.check.Check``) behind the
:class:`~pirn.nodes.gate.gate.Gate` that keeps the reflector's LLM call from
running on a successful attempt: ``Gate(input=actor, check=...)`` gates the
actor's own answer, so when this check is ``False`` the gated answer is
``Skipped`` and everything downstream of it — the reflector — is skipped
with it, never paying for the call (ADR agents-speaks-core WS5b).

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.check import Check

from pirn_agents.specializations.reflexion.reflexion_evaluation import ReflexionEvaluation


class _ShouldReflectCheck(Check):
    """``True`` when the evaluator rejected the attempt."""

    def __init__(
        self,
        *,
        evaluation: Knot | ReflexionEvaluation,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(evaluation=evaluation, _config=_config, **kwargs)

    async def process(self, evaluation: ReflexionEvaluation, **_: Any) -> bool:
        """Return whether the attempt failed and should be reflected on.

        Args:
            evaluation: The evaluator's verdict for this attempt.

        Returns:
            ``True`` when ``evaluation.success`` is ``False``.
        """
        return not evaluation.success
