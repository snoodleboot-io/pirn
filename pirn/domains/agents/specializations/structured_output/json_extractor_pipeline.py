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
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.structured_output._json_extractor_attempt import (  # noqa: E501
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
        llm: LLMProvider,
        schema: Mapping[str, Any],
        _config: KnotConfig,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "JsonExtractorPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(schema, Mapping):
            raise TypeError(
                "JsonExtractorPipeline: schema must be a Mapping, "
                f"got {type(schema).__name__}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                "JsonExtractorPipeline: max_retries must be a positive int, "
                f"got {max_retries!r}"
            )
        self._llm = llm
        self._schema = dict(schema)
        self._max_retries = max_retries
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> Mapping[str, Any]:
        """Extract a JSON mapping from the LLM response, retrying with error feedback on failure.

        Args:
            prompt: The extraction prompt string sent to the LLM.

        Returns:
            A parsed JSON mapping conforming to the configured schema.

        Raises:
            TypeError: If prompt is not a string.
            ValueError: If all retry attempts are exhausted without a valid JSON mapping.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "JsonExtractorPipeline: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        prior_error = ""
        last_error = "no attempts were made"
        for attempt_index in range(self._max_retries):
            with Tapestry() as inner:
                _JsonExtractorAttempt(
                    prompt=prompt,
                    llm=self._llm,
                    schema=self._schema,
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
            "JsonExtractorPipeline: exhausted "
            f"{self._max_retries} attempt(s); last error: {last_error}"
        )
