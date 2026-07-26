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

A provider opts into the native paths by subclassing the
:class:`StructuredOutputProvider` base; a plain
:class:`pirn_agents.llm.llm_provider.LLMProvider` simply routes to the
fallback. The convenience :func:`structured_decode` wraps a one-shot decode.
"""

from __future__ import annotations

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pydantic import BaseModel

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.structured_output.constrained_decoding_strategy import (
    ConstrainedDecodingStrategy,
)
from pirn_agents.specializations.structured_output.forced_tool_choice_strategy import (
    ForcedToolChoiceStrategy,
)
from pirn_agents.specializations.structured_output.native_decode_strategy import (
    NativeDecodeStrategy,
)
from pirn_agents.specializations.structured_output.native_schema_strategy import (
    NativeSchemaStrategy,
)
from pirn_agents.specializations.structured_output.pydantic_validator_pipeline import (
    PydanticValidatorPipeline,
)
from pirn_agents.specializations.structured_output.structured_content_validator import (
    StructuredContentValidator,
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
        validator = StructuredContentValidator(model_class=model_class)
        # Ordered by capability precedence: native_schema → forced_tool_choice →
        # constrained_decoding. A new mechanism is a new NativeDecodeStrategy
        # subclass appended here — the selection loop never changes (OCP).
        self._native_paths: tuple[NativeDecodeStrategy, ...] = (
            NativeSchemaStrategy(model_class=model_class, validator=validator),
            ForcedToolChoiceStrategy(model_class=model_class, tool_name=tool_name),
            ConstrainedDecodingStrategy(model_class=model_class, validator=validator),
        )

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
        for strategy in self._native_paths:
            if not strategy.is_advertised(capability):
                continue
            try:
                return await strategy.try_decode(prompt=prompt, provider=provider)
            except StructuredDecodeError:
                continue
        return None

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
