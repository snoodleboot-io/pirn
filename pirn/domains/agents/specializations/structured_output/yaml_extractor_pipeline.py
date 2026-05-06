"""``YamlExtractorPipeline`` — schema-targeted YAML extraction with retry.

Same shape as :class:`JsonExtractorPipeline` but YAML output. Uses
``pyyaml`` (a baseline pirn dependency). The schema is optional — when
omitted, any well-formed YAML mapping is accepted.

Algorithm:
    1. Receive ``prompt`` (str), ``llm`` (LLMProvider), optional ``schema``
       (Mapping), and ``max_retries`` (int).
    2. Validate each argument; raise ``TypeError`` or ``ValueError`` on
       invalid inputs.
    3. For each attempt index in ``range(max_retries)``:
       a. Build an inner Tapestry with a ``_YamlExtractorAttempt`` knot,
          passing the accumulated ``prior_error`` for self-correction.
       b. Await ``_run_inner`` to obtain the attempt outcome.
       c. If the outcome is a dict, return it immediately.
       d. Otherwise, record the error string and loop.
    4. Raise ``ValueError`` after exhausting all attempts.


References:
    - :class:`pirn.domains.agents.specializations.structured_output._yaml_extractor_attempt._YamlExtractorAttempt`
    - PyYAML: https://pyyaml.org/wiki/PyYAMLDocumentation
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.structured_output._yaml_extractor_attempt import (
    _YamlExtractorAttempt,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class YamlExtractorPipeline(SubTapestry):
    """LLM-driven structured YAML extraction with self-correcting retries."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        schema: Knot | Mapping[str, Any] | None = None,
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
        schema: Mapping[str, Any] | None = None,
        max_retries: int = 3,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Extract a YAML mapping from the LLM response, retrying with error feedback on failure.

        Args:
            prompt: The extraction prompt string sent to the LLM.
            llm: The LLM provider used to generate responses.
            schema: Optional mapping describing expected keys and types.
            max_retries: Maximum number of attempts before raising.

        Returns:
            A parsed YAML mapping; conforms to the optional schema when one is provided.

        Raises:
            TypeError: If any argument is the wrong type.
            ValueError: If max_retries is not a positive int, or all attempts are exhausted.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"YamlExtractorPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if schema is not None and not isinstance(schema, Mapping):
            raise TypeError(
                "YamlExtractorPipeline: schema must be a Mapping or None, "
                f"got {type(schema).__name__}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                f"YamlExtractorPipeline: max_retries must be a positive int, got {max_retries!r}"
            )
        if not isinstance(prompt, str):
            raise TypeError(
                f"YamlExtractorPipeline: prompt must be a string, got {type(prompt).__name__}"
            )
        resolved_schema: dict[str, Any] | None = dict(schema) if schema is not None else None
        prior_error = ""
        last_error = "no attempts were made"
        for attempt_index in range(max_retries):
            with Tapestry() as inner:
                _YamlExtractorAttempt(
                    prompt=prompt,
                    llm=llm,
                    schema=resolved_schema,
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
            f"YamlExtractorPipeline: exhausted {max_retries} attempt(s); last error: {last_error}"
        )
