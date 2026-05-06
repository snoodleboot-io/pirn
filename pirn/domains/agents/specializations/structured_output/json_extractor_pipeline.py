"""``JsonExtractorPipeline`` — schema-targeted JSON extraction with retry.

A :class:`SubTapestry` that asks an :class:`LLMProvider` to produce
structured JSON matching a target schema description, then parses the
response. On parse failure (invalid JSON, wrong root type, or missing
schema-declared keys) the pipeline retries up to ``max_retries`` times
with the prior parse error fed back into the next system prompt for
self-correction.

The schema is treated as a free-form mapping of expected top-level
fields. Concrete field validation is left to downstream knots —
:class:`PydanticValidatorPipeline` layers a real pydantic model on top
of this knot for strict validation.

Algorithm:
    1. Receive ``prompt``, ``llm``, ``schema``, and ``max_retries`` in :meth:`process`.
    2. Validate inputs: llm must be LLMProvider, schema a Mapping, max_retries positive.
    3. Loop up to ``max_retries`` times:
       a. Build an inner :class:`Tapestry` with a :class:`_JsonExtractorAttempt` knot.
       b. Run the tapestry; if outcome is a dict, return it immediately.
       c. Otherwise record the error string as ``prior_error`` for the next attempt.
    4. Raise :class:`ValueError` if all attempts are exhausted.


References:
    - :class:`pirn.domains.agents.llm_provider.LLMProvider`
    - :class:`pirn.domains.agents.specializations.structured_output._json_extractor_attempt._JsonExtractorAttempt`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.structured_output._json_extractor_attempt import (
    _JsonExtractorAttempt,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class JsonExtractorPipeline(SubTapestry):
    """LLM-driven structured JSON extraction with self-correcting retries."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        schema: Knot | Mapping[str, Any],
        _config: KnotConfig,
        max_retries: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prompt=prompt,
            llm=llm,
            schema=schema,
            max_retries=max_retries,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prompt: str,
        llm: LLMProvider,
        schema: Mapping[str, Any],
        max_retries: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Extract a JSON mapping from the LLM response, retrying with error feedback on failure.

        Args:
            prompt: The extraction prompt string sent to the LLM.
            llm: The LLM provider to call.
            schema: Mapping of expected top-level field names.
            max_retries: Maximum number of extraction attempts.

        Returns:
            A parsed JSON mapping conforming to the configured schema.

        Raises:
            TypeError: If llm is not an LLMProvider or prompt is not a string.
            ValueError: If schema is not a Mapping, max_retries not positive, or all attempts exhausted.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"JsonExtractorPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(schema, Mapping):
            raise TypeError(
                f"JsonExtractorPipeline: schema must be a Mapping, got {type(schema).__name__}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                f"JsonExtractorPipeline: max_retries must be a positive int, got {max_retries!r}"
            )
        if not isinstance(prompt, str):
            raise TypeError(
                f"JsonExtractorPipeline: prompt must be a string, got {type(prompt).__name__}"
            )
        schema_dict = dict(schema)
        prior_error = ""
        last_error = "no attempts were made"
        for attempt_index in range(max_retries):
            with Tapestry() as inner:
                _JsonExtractorAttempt(
                    prompt=prompt,
                    llm=llm,
                    schema=schema_dict,
                    prior_error=prior_error,
                    _config=KnotConfig(id=f"attempt_{attempt_index}"),
                )
            inner_result = await self._run_inner(inner)
            outcome = inner_result.outputs.get(f"attempt_{attempt_index}")
            if isinstance(outcome, dict):
                return outcome
            prior_error = str(outcome) if outcome is not None else "no output"
            last_error = prior_error
        raise ValueError(
            f"JsonExtractorPipeline: exhausted {max_retries} attempt(s); last error: {last_error}"
        )
