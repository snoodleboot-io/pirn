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
    4. Loop up to ``max_retries`` times:
       a. Build an inner :class:`Tapestry` with a :class:`_JsonExtractorAttempt` knot.
       b. If outcome is a dict, validate it with the model class.
       c. On success, return the validated model instance.
       d. On validation failure, record the error string as ``prior_error``.
    5. Raise :class:`ValueError` if all attempts are exhausted.


References:
    - pydantic :class:`BaseModel`:
      https://docs.pydantic.dev/latest/api/base_model/
    - :class:`pirn.domains.agents.specializations.structured_output._json_extractor_attempt._JsonExtractorAttempt`
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.specializations.structured_output._json_extractor_attempt import (
    _JsonExtractorAttempt,
)
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class PydanticValidatorPipeline(SubTapestry):
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
    ) -> Any:
        """Extract JSON from the LLM, validate against the model class, and return the validated instance.

        Args:
            prompt: The extraction prompt string sent to the LLM.
            llm: The LLM provider to call.
            model_class: The pydantic BaseModel subclass to validate against.
            max_retries: Maximum number of extraction + validation attempts.

        Returns:
            A validated model instance produced by model_class.model_validate.

        Raises:
            TypeError: If llm is not an LLMProvider, model_class not a BaseModel subclass,
                or prompt is not a string.
            ValueError: If max_retries is not positive or all attempts are exhausted.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"PydanticValidatorPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
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
        if not isinstance(prompt, str):
            raise TypeError(
                f"PydanticValidatorPipeline: prompt must be a string, got {type(prompt).__name__}"
            )
        schema = self._derive_schema(model_class)
        prior_error = ""
        last_error = "no attempts were made"
        validated_instance: BaseModel | None = None
        for attempt_index in range(max_retries):
            with Tapestry() as attempt_tapestry:
                _JsonExtractorAttempt(
                    prompt=prompt,
                    llm=llm,
                    schema=schema,
                    prior_error=prior_error,
                    _config=KnotConfig(id=f"extract_{attempt_index}"),
                )
            inner_result = await self._run_inner(attempt_tapestry)
            outcome = inner_result.outputs.get(f"extract_{attempt_index}")
            if not isinstance(outcome, dict):
                prior_error = str(outcome) if outcome is not None else "no output"
                last_error = prior_error
                continue
            try:
                validated_instance = model_class.model_validate(outcome)
                break
            except ValidationError as exc:
                prior_error = self._summarise_validation_error(exc)
                last_error = prior_error
        if validated_instance is None:
            raise ValueError(
                "PydanticValidatorPipeline: exhausted "
                f"{max_retries} attempt(s); last error: {last_error}"
            )
        _instance = validated_instance

        class _ResultSource(Source):
            async def process(self, **_: Any) -> BaseModel:
                return _instance

        return _ResultSource(_config=KnotConfig(id="result"))

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
