"""``ReflexionResultExtractor`` — final loop state to the public :class:`ReflexionResult`.

Replaces the inline ``_ReflexionResultSource(Source)`` that closed over an
already-computed :class:`ReflexionResult` (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory: a "returns inline Source" bypass).

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.reflexion.reflexion_result import ReflexionResult
from pirn_agents.specializations.reflexion.reflexion_state import ReflexionState


class ReflexionResultExtractor(Knot):
    """Convert the loop's final state into the pipeline's public :class:`ReflexionResult`."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: ReflexionState, **_: Any) -> ReflexionResult:
        """Wrap the loop's final accumulated state as a :class:`ReflexionResult`.

        Args:
            state: The loop's final accumulated state.

        Returns:
            The :class:`ReflexionResult` for the whole run.
        """
        return ReflexionResult(
            answer=state.final_answer,
            succeeded=state.succeeded,
            iterations=state.index,
            attempts=state.attempts,
        )
