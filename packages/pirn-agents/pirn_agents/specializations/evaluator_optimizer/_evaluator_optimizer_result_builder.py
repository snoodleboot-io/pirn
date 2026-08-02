"""``_EvaluatorOptimizerResultBuilder`` — final loop state to the public result.

The loop's output is the accumulated state; the pipeline's contract is an
:class:`EvaluatorOptimizerResult`. This knot is the conversion, so the pipeline
can return a real sink rather than a ``Source`` closure wrapping a precomputed
value.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.evaluator_optimizer._evaluator_optimizer_state import (
    _EvaluatorOptimizerState,
)
from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_result import (
    EvaluatorOptimizerResult,
)


class _EvaluatorOptimizerResultBuilder(Knot):
    """Convert the loop's final state into the pipeline's public result."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: Any, **_: Any) -> EvaluatorOptimizerResult:
        """Build the typed result.

        Args:
            state: The loop's final accumulated state.

        Returns:
            An :class:`EvaluatorOptimizerResult`.

        Raises:
            TypeError: If ``state`` is not the loop's state object.
        """
        if not isinstance(state, _EvaluatorOptimizerState):
            raise TypeError(
                "_EvaluatorOptimizerResultBuilder: state must be an "
                f"_EvaluatorOptimizerState, got {type(state).__name__}"
            )
        return EvaluatorOptimizerResult(
            answer=state.best_answer,
            score=state.best_score,
            accepted=state.accepted,
            iterations=state.iterations,
        )
