# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
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
    3. Drive the attempts with a :class:`JsonExtractorLoop`
       (``LoopSubTapestry``): each attempt is one real, individually-traceable
       :class:`JsonExtractorAttempt` invocation rather than a step inside a
       hand-rolled Python ``for`` loop (ADR agents-speaks-core WS5b).
    4. Extract the parsed mapping with :class:`JsonExtractorResultExtractor`,
       which raises ``ValueError`` if every attempt was exhausted.


References:
    - :class:`pirn_agents.llm.llm_provider.LLMProvider`
    - :class:`pirn_agents.specializations.structured_output._json_extractor_attempt.JsonExtractorAttempt`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.structured_output._json_extractor_loop import (
    JsonExtractorLoop,
)
from pirn_agents.specializations.structured_output._json_extractor_result_extractor import (
    JsonExtractorResultExtractor,
)
from pirn_agents.specializations.structured_output._json_extractor_state import (
    JsonExtractorState,
)


class JsonExtractorPipeline(AgentPipeline):
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
    ) -> Knot:
        """Extract a JSON mapping from the LLM response, retrying with error feedback on failure.

        Args:
            prompt: The extraction prompt string sent to the LLM.
            llm: The LLM provider to call.
            schema: Mapping of expected top-level field names.
            max_retries: Maximum number of extraction attempts.

        Returns:
            The sink knot whose output is a parsed JSON mapping conforming to
            the configured schema.

        Raises:
            TypeError: If llm is not an LLMProvider or prompt is not a string.
            ValueError: If schema is not a Mapping, max_retries not positive, or all attempts exhausted.
        """
        if not isinstance(schema, Mapping):
            raise TypeError(
                f"JsonExtractorPipeline: schema must be a Mapping, got {type(schema).__name__}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                f"JsonExtractorPipeline: max_retries must be a positive int, got {max_retries!r}"
            )
        schema_dict = dict(schema)

        initial = Parameter(
            "json_extractor_state",
            JsonExtractorState,
            default=JsonExtractorState(
                prior_error="", result=None, last_error="no attempts were made", attempts=0
            ),
        )
        loop = JsonExtractorLoop(
            prompt=prompt,
            llm=llm,
            schema=schema_dict,
            max_retries=max_retries,
            state=initial,
            _config=KnotConfig(id="json_extractor_loop"),
        )
        return JsonExtractorResultExtractor(state=loop, _config=KnotConfig(id="result"))
