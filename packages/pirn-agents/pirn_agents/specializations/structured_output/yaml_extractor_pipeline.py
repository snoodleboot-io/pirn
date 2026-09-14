# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``YamlExtractorPipeline`` — schema-targeted YAML extraction with retry.

Same shape as :class:`JsonExtractorPipeline` but YAML output. Uses
``pyyaml`` (a baseline pirn dependency). The schema is optional — when
omitted, any well-formed YAML mapping is accepted.

Algorithm:
    1. Receive ``prompt`` (str), ``llm`` (LLMProvider), optional ``schema``
       (Mapping), and ``max_retries`` (int).
    2. Validate each argument; raise ``TypeError`` or ``ValueError`` on
       invalid inputs.
    3. Drive the attempts with a ``YamlExtractorLoop`` (``LoopSubTapestry``):
       each attempt is one real, individually-traceable
       ``YamlExtractorAttempt`` invocation, passing the accumulated
       ``prior_error`` for self-correction, rather than a step inside a
       hand-rolled Python ``for`` loop (ADR agents-speaks-core WS5b).
    4. Extract the parsed mapping with ``YamlExtractorResultExtractor``,
       which raises ``ValueError`` if every attempt was exhausted.


References:
    - :class:`pirn_agents.specializations.structured_output._yaml_extractor_attempt.YamlExtractorAttempt`
    - PyYAML: https://pyyaml.org/wiki/PyYAMLDocumentation
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.structured_output._yaml_extractor_loop import (
    YamlExtractorLoop,
)
from pirn_agents.specializations.structured_output._yaml_extractor_result_extractor import (
    YamlExtractorResultExtractor,
)
from pirn_agents.specializations.structured_output._yaml_extractor_state import (
    YamlExtractorState,
)


class YamlExtractorPipeline(AgentPipeline):
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
    ) -> Knot:
        """Extract a YAML mapping from the LLM response, retrying with error feedback on failure.

        Args:
            prompt: The extraction prompt string sent to the LLM.
            llm: The LLM provider used to generate responses.
            schema: Optional mapping describing expected keys and types.
            max_retries: Maximum number of attempts before raising.

        Returns:
            The sink knot whose output is a parsed YAML mapping; conforms to
            the optional schema when one is provided.

        Raises:
            TypeError: If any argument is the wrong type.
            ValueError: If max_retries is not a positive int, or all attempts are exhausted.
        """
        if schema is not None and not isinstance(schema, Mapping):
            raise TypeError(
                "YamlExtractorPipeline: schema must be a Mapping or None, "
                f"got {type(schema).__name__}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                f"YamlExtractorPipeline: max_retries must be a positive int, got {max_retries!r}"
            )
        resolved_schema: dict[str, Any] | None = dict(schema) if schema is not None else None

        initial = Parameter(
            "yaml_extractor_state",
            YamlExtractorState,
            default=YamlExtractorState(
                prior_error="", result=None, last_error="no attempts were made", attempts=0
            ),
        )
        loop = YamlExtractorLoop(
            prompt=prompt,
            llm=llm,
            schema=resolved_schema,
            max_retries=max_retries,
            state=initial,
            _config=KnotConfig(id="yaml_extractor_loop"),
        )
        return YamlExtractorResultExtractor(state=loop, _config=KnotConfig(id="result"))
