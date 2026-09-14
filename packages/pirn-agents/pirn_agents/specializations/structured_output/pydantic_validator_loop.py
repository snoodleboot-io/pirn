"""``PydanticValidatorLoop`` — the extract-and-validate retry loop as a core node.

Replaces the hand-rolled ``for attempt_index in range(max_retries): ...
await self._run_inner(...)`` that ran every attempt through a Python loop
inside ``process()``, so each attempt is an engine knot with its own
``Result``, history record, and lineage (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory).

``model_class.model_validate`` is a synchronous, in-process call (no LLM or
tool call), so it runs inside ``fold`` -- exactly where the original ran it
inside the Python loop body -- mirroring how ``RetryOnParseFailureLoop``
runs its ``parser`` callable in ``fold``.

Internal API. See PIR-856.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pydantic import BaseModel, ValidationError

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.structured_output.json_extractor_attempt import (
    JsonExtractorAttempt,
)
from pirn_agents.specializations.structured_output.pydantic_validator_state import (
    PydanticValidatorState,
)

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class PydanticValidatorLoop(AgentLoopPipeline[PydanticValidatorState]):
    """Retry extraction + validation, feeding the error back, until it succeeds or is exhausted."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _extract_id: ClassVar[str] = "extract"

    def __init__(
        self,
        *,
        prompt: str,
        llm: LLMProvider,
        schema: Mapping[str, Any],
        model_class: type[BaseModel],
        max_retries: int,
        **kwargs: Any,
    ) -> None:
        self._prompt = prompt
        self._llm = llm
        self._schema = schema
        self._model_class = model_class
        self._max_retries = max_retries
        super().__init__(**kwargs)

    def step(self, state: PydanticValidatorState) -> tuple[Tapestry, PydanticValidatorState] | None:
        """Build the next attempt, or return None once validated or exhausted.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` once
            ``state.validated`` is set or ``state.attempts`` has reached the cap.
        """
        if state.validated is not None or state.attempts >= self._max_retries:
            return None

        attempt = Tapestry()
        with attempt:
            JsonExtractorAttempt(
                prompt=self._prompt,
                llm=self._llm,
                schema=self._schema,
                prior_error=state.prior_error,
                _config=KnotConfig(id=self._extract_id),
            )
        return attempt, state

    def fold(self, state: PydanticValidatorState, result: RunResult) -> PydanticValidatorState:
        """Validate the extracted mapping; record success or the error to feed back.

        Args:
            state: State as ``step`` returned it.
            result: The attempt's run result.

        Returns:
            A new state carrying the validated instance on success, or the
            error for the next attempt's self-correction.
        """
        outcome = result.outputs[self._extract_id]
        if not isinstance(outcome, dict):
            error = str(outcome) if outcome is not None else "no output"
            return PydanticValidatorState(
                prior_error=error, validated=None, last_error=error, attempts=state.attempts + 1
            )
        try:
            validated = self._model_class.model_validate(outcome)
        except ValidationError as exc:
            error = self._summarise_validation_error(exc)
            return PydanticValidatorState(
                prior_error=error, validated=None, last_error=error, attempts=state.attempts + 1
            )
        return PydanticValidatorState(
            prior_error=state.prior_error,
            validated=validated,
            last_error=state.last_error,
            attempts=state.attempts + 1,
        )

    def step_id(self, state: PydanticValidatorState, idx: int) -> str:
        """Name each attempt for run history."""
        return f"extract_{idx}"

    @staticmethod
    def _summarise_validation_error(exc: ValidationError) -> str:
        try:
            errors = exc.errors()
        except Exception:
            return str(exc)
        try:
            return f"pydantic validation failed: {json.dumps(errors)}"
        except (TypeError, ValueError):
            return f"pydantic validation failed: {errors!r}"
