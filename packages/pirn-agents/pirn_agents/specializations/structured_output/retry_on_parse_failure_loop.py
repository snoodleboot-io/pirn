"""``RetryOnParseFailureLoop`` — the parse-retry loop as a core node.

Replaces the hand-rolled ``for attempt_index in range(max_retries): ...
try/except`` that ran every attempt through its own ``_run_inner`` call
inside a Python loop, so each attempt is an engine knot with its own
``Result``, history record, and lineage (ADR agents-speaks-core WS5a;
PIR-856's imperative-loop inventory).

``parser`` is a plain callable, not a knot: it runs synchronously inside
``fold``, exactly where the original ran it inside the Python loop body — no
LLM or tool call happens there, so this does not reintroduce the shape the
ADR is removing.

Internal API. See PIR-856.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.structured_output.llm_call_knot import LLMCallKnot
from pirn_agents.specializations.structured_output.retry_state import RetryState

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class RetryOnParseFailureLoop(AgentLoopPipeline[RetryState]):
    """Retry the LLM call, feeding the parse error back, until it parses or is exhausted."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _call_id: ClassVar[str] = "call"

    def step(self, state: RetryState) -> tuple[Tapestry, RetryState] | None:
        """Build the next attempt, or return None once parsed or exhausted.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` once
            ``state.succeeded`` or ``state.attempts`` has reached the cap.
        """
        if state.succeeded or state.attempts >= state.max_retries:
            return None

        attempt = Tapestry()
        with attempt:
            LLMCallKnot(
                prompt=state.prompt,
                llm=state.llm,
                _config=KnotConfig(id=self._call_id),
            )
        return attempt, state

    def fold(self, state: RetryState, result: RunResult) -> RetryState:
        """Try to parse the attempt's raw text; feed a failure back as context.

        Args:
            state: State as ``step`` returned it.
            result: The attempt's run result.

        Returns:
            A new state carrying the parsed value on success, or a retry
            prompt naming the failure on parse error.
        """
        text = result.outputs.get(self._call_id)
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        try:
            parsed = state.parser(text)
        except Exception as exc:
            last_error = str(exc)
            retry_prompt = (
                f"{state.original_prompt}\n\nPrevious attempt failed with: {last_error}\n"
                "Please fix the issue and try again."
            )
            return replace(
                state,
                prompt=retry_prompt,
                parsed_value=None,
                succeeded=False,
                last_error=last_error,
                attempts=state.attempts + 1,
            )
        return replace(state, parsed_value=parsed, succeeded=True, attempts=state.attempts + 1)

    def step_id(self, state: RetryState, idx: int) -> str:
        """Name each attempt for run history."""
        return f"attempt_{idx}"
