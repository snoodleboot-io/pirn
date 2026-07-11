"""``StructuredDecoder`` — the unified, capability-gated structured-output API.

The S4 entry point. Given a prompt, an LLM provider, and a target pydantic
model, it selects the best available single-pass mechanism in capability order —
native schema decoding (S1), forced tool-choice extraction (S2), then
grammar/regex-constrained decoding (S3) — and transparently falls back to the
existing extract-validate-retry pipeline
(:class:`pirn_agents.specializations.structured_output.pydantic_validator_pipeline.PydanticValidatorPipeline`)
when no native path is available or a selected path cannot produce a valid
instance. Every route returns the *same* validated pydantic instance, so callers
get typed results end-to-end regardless of how they were produced.

A provider opts into the native paths by implementing the
:class:`StructuredOutputProvider` protocol; a plain
:class:`pirn.core.providers.llm_provider.LLMProvider` simply routes to the
fallback. The convenience :func:`structured_decode` wraps a one-shot decode.
"""

from __future__ import annotations

import json
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pydantic import BaseModel, ValidationError

from pirn_agents.specializations.structured_output.constrained_decoding_mapper import (
    ConstrainedDecodingMapper,
)
from pirn_agents.specializations.structured_output.forced_tool_choice_extractor import (
    ForcedToolChoiceExtractor,
)
from pirn_agents.specializations.structured_output.native_schema_mapper import (
    NativeSchemaMapper,
)
from pirn_agents.specializations.structured_output.pydantic_validator_pipeline import (
    PydanticValidatorPipeline,
)
from pirn_agents.specializations.structured_output.structured_decode_error import (
    StructuredDecodeError,
)
from pirn_agents.specializations.structured_output.structured_output_provider import (
    StructuredOutputProvider,
)


class StructuredDecoder:
    """Select native → forced → constrained → retry-pipeline, returning a model."""

    def __init__(
        self,
        *,
        model_class: type[BaseModel],
        max_retries: int = 3,
        tool_name: str = "extract",
    ) -> None:
        """Bind the decoder to a target model and fallback retry budget.

        Args:
            model_class: The :class:`pydantic.BaseModel` subclass to decode.
            max_retries: Retry budget for the extract-validate-retry fallback.
            tool_name: Name of the synthetic tool used by the forced-tool path.

        Raises:
            TypeError: If ``model_class`` is not a ``BaseModel`` subclass or
                ``tool_name`` is not a non-empty string.
            ValueError: If ``max_retries`` is not a positive integer.
        """
        if not isinstance(model_class, type) or not issubclass(model_class, BaseModel):
            raise TypeError(
                f"StructuredDecoder: model_class must be a BaseModel subclass, got {model_class!r}"
            )
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries <= 0:
            raise ValueError(
                f"StructuredDecoder: max_retries must be a positive int, got {max_retries!r}"
            )
        if not isinstance(tool_name, str) or not tool_name:
            raise TypeError(
                f"StructuredDecoder: tool_name must be a non-empty str, got {tool_name!r}"
            )
        self._model_class = model_class
        self._max_retries = max_retries
        self._tool_name = tool_name

    async def decode(self, *, prompt: str, llm: LLMProvider) -> BaseModel:
        """Decode ``prompt`` into a validated model instance.

        Tries each native mechanism the provider advertises, in capability
        order, then falls back to the retry pipeline. Always returns a validated
        instance of the bound model class.

        Args:
            prompt: The prompt describing the data to produce.
            llm: The LLM provider; native paths are used only when it implements
                :class:`StructuredOutputProvider`.

        Returns:
            A validated instance of the bound model class.

        Raises:
            TypeError: If ``prompt`` is not a string or ``llm`` is not an
                :class:`LLMProvider`.
            ValueError: If the fallback pipeline exhausts all retries.
        """
        if not isinstance(prompt, str):
            raise TypeError(f"StructuredDecoder: prompt must be a str, got {type(prompt).__name__}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"StructuredDecoder: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if isinstance(llm, StructuredOutputProvider):
            native = await self._try_native_paths(prompt, llm)
            if native is not None:
                return native
        return await self._fallback(prompt, llm)

    async def _try_native_paths(
        self, prompt: str, provider: StructuredOutputProvider
    ) -> BaseModel | None:
        capability = provider.structured_output_capability()
        if capability.native_schema:
            try:
                return await self._decode_native(prompt, provider)
            except StructuredDecodeError:
                pass
        if capability.forced_tool_choice:
            try:
                return await ForcedToolChoiceExtractor(
                    model_class=self._model_class, tool_name=self._tool_name
                ).extract(prompt=prompt, provider=provider)
            except StructuredDecodeError:
                pass
        if capability.constrained_decoding:
            try:
                return await self._decode_constrained(prompt, provider)
            except StructuredDecodeError:
                pass
        return None

    async def _decode_native(self, prompt: str, provider: StructuredOutputProvider) -> BaseModel:
        options = NativeSchemaMapper(schema=self._model_class).map_request(provider)
        if options is None:
            raise StructuredDecodeError("StructuredDecoder: native schema mapping unsupported")
        response = await provider.structured_chat(
            [{"role": "user", "content": prompt}], request_options=options
        )
        return self._validate_content(response.content)

    async def _decode_constrained(
        self, prompt: str, provider: StructuredOutputProvider
    ) -> BaseModel:
        options = ConstrainedDecodingMapper(schema=self._model_class).map_request(provider)
        if options is None:
            raise StructuredDecodeError("StructuredDecoder: constrained decoding unsupported")
        response = await provider.structured_chat(
            [{"role": "user", "content": prompt}], request_options=options
        )
        return self._validate_content(response.content)

    def _validate_content(self, content: str) -> BaseModel:
        try:
            data: Any = json.loads(content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise StructuredDecodeError(
                f"StructuredDecoder: native content was not valid JSON: {exc}"
            ) from exc
        try:
            return self._model_class.model_validate(data)
        except ValidationError as exc:
            raise StructuredDecodeError(
                f"StructuredDecoder: native content failed model validation: {exc}"
            ) from exc

    async def _fallback(self, prompt: str, llm: LLMProvider) -> BaseModel:
        with Tapestry() as tapestry:
            PydanticValidatorPipeline(
                prompt=prompt,
                llm=llm,
                model_class=self._model_class,
                max_retries=self._max_retries,
                _config=KnotConfig(id="structured_fallback"),
            )
        result = await tapestry.run(RunRequest())
        if not result.succeeded:
            raise ValueError(f"StructuredDecoder: fallback pipeline failed: {result.exceptions}")
        instance = result.outputs.get("structured_fallback")
        if not isinstance(instance, self._model_class):
            raise ValueError(
                "StructuredDecoder: fallback pipeline did not produce the expected model instance"
            )
        return instance


async def structured_decode(
    *,
    prompt: str,
    llm: LLMProvider,
    model_class: type[BaseModel],
    max_retries: int = 3,
    tool_name: str = "extract",
) -> BaseModel:
    """Decode ``prompt`` into a validated ``model_class`` instance (one shot).

    A convenience wrapper constructing a :class:`StructuredDecoder` and running a
    single decode. See :meth:`StructuredDecoder.decode` for the selection order
    and fallback behavior.

    Args:
        prompt: The prompt describing the data to produce.
        llm: The LLM provider (native paths used when it is a
            :class:`StructuredOutputProvider`).
        model_class: The target :class:`pydantic.BaseModel` subclass.
        max_retries: Retry budget for the extract-validate-retry fallback.
        tool_name: Name of the synthetic tool used by the forced-tool path.

    Returns:
        A validated instance of ``model_class``.
    """
    decoder = StructuredDecoder(
        model_class=model_class, max_retries=max_retries, tool_name=tool_name
    )
    return await decoder.decode(prompt=prompt, llm=llm)
