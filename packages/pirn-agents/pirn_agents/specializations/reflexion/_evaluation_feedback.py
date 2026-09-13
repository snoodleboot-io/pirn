"""``_EvaluationFeedback`` — project the evaluator's feedback string.

The reflector needs ``feedback`` as a bare string (Rule 2:
``knot-design-rules.md``), not the whole
:class:`~pirn_agents.specializations.reflexion.reflexion_evaluation.ReflexionEvaluation`;
this knot is that projection.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.reflexion.reflexion_evaluation import ReflexionEvaluation


class _EvaluationFeedback(Knot):
    """Project ``evaluation.feedback`` as a bare string."""

    def __init__(
        self,
        *,
        evaluation: Knot | ReflexionEvaluation,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(evaluation=evaluation, _config=_config, **kwargs)

    async def process(self, evaluation: ReflexionEvaluation, **_: Any) -> str:
        """Return the evaluator's feedback string.

        Args:
            evaluation: The evaluator's verdict for this attempt.

        Returns:
            ``evaluation.feedback``.
        """
        return evaluation.feedback
