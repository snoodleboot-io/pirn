"""Tests for the unified :class:`StructuredDecoder` / :func:`structured_decode` (F20-S4)."""

from __future__ import annotations

import unittest

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.structured_decoder import (
    StructuredDecoder,
    structured_decode,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from tests.specializations.conftest import StubLLMProvider
from tests.specializations.structured_output.structured_stubs import (
    StubStructuredProvider,
    content_response,
    tool_call_response,
)


class _UserRecord(BaseModel):
    name: str
    age: int


_VALID_JSON = '{"name": "Ada", "age": 36}'


class TestStructuredDecoderNativePaths(unittest.IsolatedAsyncioTestCase):
    async def test_native_schema_success(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(native_schema=True),
            structured_response=content_response(_VALID_JSON),
        )
        decoder = StructuredDecoder(model_class=_UserRecord)

        instance = await decoder.decode(prompt="extract", llm=provider)

        assert isinstance(instance, _UserRecord)
        assert instance.age == 36
        # Native path used: exactly one structured call carrying response_format.
        assert len(provider.structured_calls) == 1
        assert "response_format" in provider.structured_calls[0]["request_options"]
        assert provider.chat_calls == []

    async def test_forced_tool_choice_success(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(forced_tool_choice=True),
            structured_response=tool_call_response({"name": "Grace", "age": 45}),
        )
        decoder = StructuredDecoder(model_class=_UserRecord)

        instance = await decoder.decode(prompt="extract", llm=provider)

        assert isinstance(instance, _UserRecord)
        assert instance.name == "Grace"
        assert "tool_choice" in provider.structured_calls[0]["request_options"]

    async def test_constrained_decoding_success(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(constrained_decoding=True),
            structured_response=content_response(_VALID_JSON),
        )
        decoder = StructuredDecoder(model_class=_UserRecord)

        instance = await decoder.decode(prompt="extract", llm=provider)

        assert isinstance(instance, _UserRecord)
        assert "extra_body" in provider.structured_calls[0]["request_options"]


class TestStructuredDecoderFallback(unittest.IsolatedAsyncioTestCase):
    async def test_plain_provider_falls_back_to_retry_pipeline(self) -> None:
        # A plain LLMProvider advertises no capability → straight to fallback.
        llm = StubLLMProvider([_VALID_JSON])
        decoder = StructuredDecoder(model_class=_UserRecord)

        instance = await decoder.decode(prompt="extract", llm=llm)

        assert isinstance(instance, _UserRecord)
        assert instance.name == "Ada"
        assert len(llm.calls) == 1

    async def test_native_failure_falls_back_to_retry_pipeline(self) -> None:
        # Native path is available but returns invalid content; the decoder must
        # gracefully fall back to the extract-validate-retry pipeline.
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(native_schema=True),
            structured_response=content_response("not json at all"),
            chat_responses=[_VALID_JSON],
        )
        decoder = StructuredDecoder(model_class=_UserRecord)

        instance = await decoder.decode(prompt="extract", llm=provider)

        assert isinstance(instance, _UserRecord)
        assert len(provider.structured_calls) == 1  # native attempted once
        assert len(provider.chat_calls) == 1  # then fell back

    async def test_capability_all_false_falls_back(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(),
            chat_responses=[_VALID_JSON],
        )
        decoder = StructuredDecoder(model_class=_UserRecord)

        instance = await decoder.decode(prompt="extract", llm=provider)

        assert isinstance(instance, _UserRecord)
        assert provider.structured_calls == []
        assert len(provider.chat_calls) == 1


class TestStructuredDecodeFunction(unittest.IsolatedAsyncioTestCase):
    async def test_unified_entrypoint_returns_instance(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(native_schema=True),
            structured_response=content_response(_VALID_JSON),
        )

        instance = await structured_decode(prompt="extract", llm=provider, model_class=_UserRecord)

        assert isinstance(instance, _UserRecord)
        assert instance.age == 36


class TestStructuredDecoderValidation(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_basemodel(self) -> None:
        with self.assertRaisesRegex(TypeError, "model_class must be a BaseModel"):
            StructuredDecoder(model_class=int)  # type: ignore[type-var]

    def test_rejects_zero_max_retries(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_retries"):
            StructuredDecoder(model_class=_UserRecord, max_retries=0)

    def test_rejects_empty_tool_name(self) -> None:
        with self.assertRaisesRegex(TypeError, "tool_name"):
            StructuredDecoder(model_class=_UserRecord, tool_name="")

    async def test_rejects_non_string_prompt(self) -> None:
        decoder = StructuredDecoder(model_class=_UserRecord)
        with self.assertRaisesRegex(TypeError, "prompt must be"):
            await decoder.decode(prompt=123, llm=StubLLMProvider([_VALID_JSON]))  # type: ignore[arg-type]

    async def test_rejects_non_provider_llm(self) -> None:
        decoder = StructuredDecoder(model_class=_UserRecord)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await decoder.decode(prompt="x", llm=object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
