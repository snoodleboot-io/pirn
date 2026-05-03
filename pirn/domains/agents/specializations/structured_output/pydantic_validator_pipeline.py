"""``PydanticValidatorPipeline`` — JSON extraction + pydantic validation.

A :class:`SubTapestry` that wraps :class:`JsonExtractorPipeline`, feeds
the extracted JSON into a caller-supplied :class:`pydantic.BaseModel`
subclass, and returns the validated model instance. Validation errors
trigger another extraction attempt (the pydantic error string is fed
back into the next system prompt for self-correction).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.structured_output._json_extractor_attempt import (  # noqa: E501
    _JsonExtractorAttempt,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class PydanticValidatorPipeline(SubTapestry):
    """Extract JSON, validate against a :class:`BaseModel`, retry on failure."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        model_class: type[BaseModel],
        _config: KnotConfig,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "PydanticValidatorPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(model_class, type) or not issubclass(
            model_class, BaseModel
        ):
            raise TypeError(
                "PydanticValidatorPipeline: model_class must be a BaseModel "
                f"subclass, got {model_class!r}"
            )
        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(
                "PydanticValidatorPipeline: max_retries must be a positive int, "
                f"got {max_retries!r}"
            )
        self._llm = llm
        self._model_class = model_class
        self._max_retries = max_retries
        self._schema = self._derive_schema(model_class)
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> BaseModel:
        """Extract JSON from the LLM, validate against the model class, and return the validated instance.

        Args:
            prompt: The extraction prompt string sent to the LLM.

        Returns:
            A validated model instance produced by model_class.model_validate.

        Raises:
            TypeError: If prompt is not a string.
            ValueError: If all retry attempts are exhausted without a valid model instance.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "PydanticValidatorPipeline: prompt must be a string, "
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
                    _config=KnotConfig(id=f"extract_{attempt_index}"),
                )
            inner_result = await self._run_inner(inner)
            outcome = inner_result.outputs.get(f"extract_{attempt_index}")
            if not isinstance(outcome, dict):
                prior_error = (
                    str(outcome) if outcome is not None else "no output"
                )
                last_error = prior_error
                continue
            try:
                return self._model_class.model_validate(outcome)
            except ValidationError as exc:
                prior_error = self._summarise_validation_error(exc)
                last_error = prior_error
        raise ValueError(
            "PydanticValidatorPipeline: exhausted "
            f"{self._max_retries} attempt(s); last error: {last_error}"
        )

    @staticmethod
    def _derive_schema(model_class: type[BaseModel]) -> Mapping[str, Any]:
        try:
            full_schema = model_class.model_json_schema()
        except Exception:
            return {}
        properties = full_schema.get("properties")
        if isinstance(properties, dict):
            return {
                str(name): {"type": spec.get("type", "any")}
                if isinstance(spec, dict)
                else {"type": "any"}
                for name, spec in properties.items()
            }
        return {}

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
