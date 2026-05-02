"""``YamlExtractorPipeline`` — schema-targeted YAML extraction with retry.

Same shape as :class:`JsonExtractorPipeline` but YAML output. Uses
``pyyaml`` (a baseline pirn dependency). The schema is optional — when
omitted, any well-formed YAML mapping is accepted.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.structured_output._yaml_extractor_attempt import (  # noqa: E501
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
        llm: LLMProvider,
        _config: KnotConfig,
        schema: Mapping[str, Any] | None = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "YamlExtractorPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if schema is not None and not isinstance(schema, Mapping):
            raise TypeError(
                "YamlExtractorPipeline: schema must be a Mapping or None, "
                f"got {type(schema).__name__}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                "YamlExtractorPipeline: max_retries must be a positive int, "
                f"got {max_retries!r}"
            )
        self._llm = llm
        self._schema: dict[str, Any] | None = (
            dict(schema) if schema is not None else None
        )
        self._max_retries = max_retries
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> Mapping[str, Any]:
        if not isinstance(prompt, str):
            raise TypeError(
                "YamlExtractorPipeline: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        prior_error = ""
        last_error = "no attempts were made"
        for attempt_index in range(self._max_retries):
            with Tapestry() as inner:
                _YamlExtractorAttempt(
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
            "YamlExtractorPipeline: exhausted "
            f"{self._max_retries} attempt(s); last error: {last_error}"
        )
