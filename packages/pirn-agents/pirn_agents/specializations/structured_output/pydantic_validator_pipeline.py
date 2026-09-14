# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style
"""``PydanticValidatorPipeline`` — JSON extraction + pydantic validation.

A :class:`SubTapestry` that wraps :class:`JsonExtractorPipeline`, feeds
the extracted JSON into a caller-supplied :class:`pydantic.BaseModel`
subclass, and returns the validated model instance. Validation errors
trigger another extraction attempt (the pydantic error string is fed
back into the next system prompt for self-correction).

Algorithm:
    1. Receive ``prompt``, ``llm``, ``model_class``, and ``max_retries`` in :meth:`process`.
    2. Validate inputs: llm must be LLMProvider, model_class a BaseModel subclass, max_retries positive.
    3. Derive a schema dict from the model class's JSON schema.
    4. Drive the attempts with a :class:`PydanticValidatorLoop`
       (``LoopSubTapestry``): each attempt is one real, individually-traceable
       :class:`JsonExtractorAttempt` invocation, validated against
       ``model_class`` in ``fold``, rather than a step inside a hand-rolled
       Python ``for`` loop (ADR agents-speaks-core WS5b).
    5. Extract the validated instance with
       :class:`PydanticValidatorResultExtractor`, which raises
       :class:`ValueError` if every attempt was exhausted.


References:
    - pydantic :class:`BaseModel`:
      https://docs.pydantic.dev/latest/api/base_model/
    - :class:`pirn_agents.specializations.structured_output.json_extractor_attempt.JsonExtractorAttempt`
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pydantic import BaseModel

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.structured_output.pydantic_validator_loop import (
    PydanticValidatorLoop,
)
from pirn_agents.specializations.structured_output.pydantic_validator_result_extractor import (
    PydanticValidatorResultExtractor,
)
from pirn_agents.specializations.structured_output.pydantic_validator_state import (
    PydanticValidatorState,
)


class PydanticValidatorPipeline(AgentPipeline):
    """Extract JSON, validate against a :class:`BaseModel`, retry on failure."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        model_class: Knot | type[BaseModel],
        _config: KnotConfig,
        max_retries: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prompt=prompt,
            llm=llm,
            model_class=model_class,
            max_retries=max_retries,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        prompt: str,
        llm: LLMProvider,
        model_class: type[BaseModel],
        max_retries: int,
        **_: Any,
    ) -> Knot:
        """Extract JSON from the LLM, validate against the model class, and return the validated instance.

        Args:
            prompt: The extraction prompt string sent to the LLM.
            llm: The LLM provider to call.
            model_class: The pydantic BaseModel subclass to validate against.
            max_retries: Maximum number of extraction + validation attempts.

        Returns:
            The sink knot whose output is a validated model instance produced
            by ``model_class.model_validate``.

        Raises:
            TypeError: If llm is not an LLMProvider, model_class not a BaseModel subclass,
                or prompt is not a string.
            ValueError: If max_retries is not positive or all attempts are exhausted.
        """
        if not isinstance(model_class, type) or not issubclass(model_class, BaseModel):
            raise TypeError(
                "PydanticValidatorPipeline: model_class must be a BaseModel "
                f"subclass, got {model_class!r}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                "PydanticValidatorPipeline: max_retries must be a positive int, "
                f"got {max_retries!r}"
            )
        schema = self._derive_schema(model_class)

        initial = Parameter(
            "pydantic_validator_state",
            PydanticValidatorState,
            default=PydanticValidatorState(
                prior_error="", validated=None, last_error="no attempts were made", attempts=0
            ),
        )
        loop = PydanticValidatorLoop(
            prompt=prompt,
            llm=llm,
            schema=schema,
            model_class=model_class,
            max_retries=max_retries,
            state=initial,
            _config=KnotConfig(id="pydantic_validator_loop"),
        )
        return PydanticValidatorResultExtractor(state=loop, _config=KnotConfig(id="result"))

    @staticmethod
    def _derive_schema(model_class: type[BaseModel]) -> Mapping[str, Any]:
        try:
            full_schema = model_class.model_json_schema()
        except Exception:
            return {}
        match full_schema.get("properties"):
            case {**properties}:
                return {
                    str(name): PydanticValidatorPipeline._field_type(spec)
                    for name, spec in properties.items()
                }
            case _:
                return {}

    @staticmethod
    def _field_type(spec: Any) -> dict[str, Any]:
        """Project one JSON-Schema property onto its ``{"type": ...}`` entry."""
        match spec:
            case {"type": field_type}:
                return {"type": field_type}
            case _:
                return {"type": "any"}
