"""``YamlExtractorLoop`` — the extraction-retry loop as a core node.

Replaces the hand-rolled ``for attempt_index in range(max_retries): ...
await self._run_inner(...)`` that ran every attempt through a Python loop
inside ``process()``, so each attempt is an engine knot with its own
``Result``, history record, and lineage (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory).

Internal API. See PIR-856.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.structured_output.yaml_extractor_attempt import (
    YamlExtractorAttempt,
)
from pirn_agents.specializations.structured_output.yaml_extractor_state import (
    YamlExtractorState,
)

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class YamlExtractorLoop(AgentLoopPipeline[YamlExtractorState]):
    """Retry the extraction attempt, feeding the parse error back, until it succeeds or is exhausted."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _attempt_id: ClassVar[str] = "attempt"

    def step(self, state: YamlExtractorState) -> tuple[Tapestry, YamlExtractorState] | None:
        """Build the next attempt, or return None once parsed or exhausted.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` once
            ``state.result`` is set or ``state.attempts`` has reached the cap.
        """
        if state.result is not None or state.attempts >= state.max_retries:
            return None

        attempt = Tapestry()
        with attempt:
            YamlExtractorAttempt(
                prompt=state.prompt,
                llm=state.llm,
                schema=state.schema,
                prior_error=state.prior_error,
                _config=KnotConfig(id=self._attempt_id),
            )
        return attempt, state

    def fold(self, state: YamlExtractorState, result: RunResult) -> YamlExtractorState:
        """Record success, or the error to feed back as the next attempt's context.

        Args:
            state: State as ``step`` returned it.
            result: The attempt's run result.

        Returns:
            A new state carrying the parsed mapping on success, or the error
            for the next attempt's self-correction.
        """
        outcome = result.outputs[self._attempt_id]
        match outcome:
            case {**parsed}:
                return replace(state, result=parsed, attempts=state.attempts + 1)
            case _:
                pass
        error = str(outcome) if outcome is not None else "no output"
        return replace(
            state,
            prior_error=error,
            result=None,
            last_error=error,
            attempts=state.attempts + 1,
        )

    def step_id(self, state: YamlExtractorState, idx: int) -> str:
        """Name each attempt for run history."""
        return f"attempt_{idx}"
