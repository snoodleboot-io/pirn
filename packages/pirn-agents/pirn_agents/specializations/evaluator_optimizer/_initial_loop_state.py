"""``_InitialLoopState`` — seeds the refine loop's state.

``LoopSubTapestry`` takes its starting state as a parent knot, so the initial
value needs a ``Source`` to produce it.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.nodes.source import Source

from pirn_agents.specializations.evaluator_optimizer._evaluator_optimizer_state import (
    _EvaluatorOptimizerState,
)


class _InitialLoopState(Source):
    """Produce the loop's zero state."""

    async def process(self, **_: Any) -> _EvaluatorOptimizerState:
        """Return the starting state.

        Returns:
            An :class:`_EvaluatorOptimizerState` with no iterations recorded.
        """
        return _EvaluatorOptimizerState()
