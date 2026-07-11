"""Tests for :class:`ForcedToolChoiceExtractor` (F20-S2)."""

from __future__ import annotations

import unittest

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.forced_tool_choice_extractor import (
    ForcedToolChoiceExtractor,
)
from pirn_agents.specializations.structured_output.structured_decode_error import (
    StructuredDecodeError,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.structured_output.structured_stubs import (
    StubStructuredProvider,
    tool_call_response,
)


class _UserRecord(BaseModel):
    name: str
    age: int


class TestForcedToolChoiceExtractorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_forces_tool_choice_and_returns_validated_model(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(forced_tool_choice=True),
            structured_response=tool_call_response({"name": "Ada", "age": 36}),
        )
        extractor = ForcedToolChoiceExtractor(model_class=_UserRecord)

        instance = await extractor.extract(prompt="extract a user", provider=provider)

        assert isinstance(instance, _UserRecord)
        assert instance.name == "Ada"
        assert instance.age == 36
        # A single forced call, with the synthetic tool declared and forced.
        assert len(provider.structured_calls) == 1
        call = provider.structured_calls[0]
        assert call["request_options"] == {"tool_choice": {"name": "extract"}}
        toolset = call["tools"]
        assert toolset is not None
        assert [tool.name for tool in toolset] == ["extract"]

    async def test_synthetic_tool_schema_is_the_model_schema(self) -> None:
        extractor = ForcedToolChoiceExtractor(model_class=_UserRecord)

        toolset = extractor.toolset()

        tool = toolset.get("extract")
        assert tool is not None
        assert set(tool.parameters_schema["properties"]) == {"name", "age"}


class TestForcedToolChoiceExtractorErrors(unittest.IsolatedAsyncioTestCase):
    async def test_capability_absent_raises_decode_error(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(forced_tool_choice=False),
            structured_response=tool_call_response({"name": "Ada", "age": 36}),
        )
        extractor = ForcedToolChoiceExtractor(model_class=_UserRecord)

        with self.assertRaisesRegex(StructuredDecodeError, "does not advertise"):
            await extractor.extract(prompt="x", provider=provider)

    async def test_no_tool_call_raises_decode_error(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(forced_tool_choice=True),
            structured_response=AgentResponse(content="no tools here"),
        )
        extractor = ForcedToolChoiceExtractor(model_class=_UserRecord)

        with self.assertRaisesRegex(StructuredDecodeError, "no tool call"):
            await extractor.extract(prompt="x", provider=provider)

    async def test_invalid_arguments_raise_decode_error(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(forced_tool_choice=True),
            structured_response=tool_call_response({"name": "Ada", "age": "old"}),
        )
        extractor = ForcedToolChoiceExtractor(model_class=_UserRecord)

        with self.assertRaisesRegex(StructuredDecodeError, "failed validation"):
            await extractor.extract(prompt="x", provider=provider)

    async def test_rejects_non_basemodel(self) -> None:
        with self.assertRaisesRegex(TypeError, "model_class must be a BaseModel"):
            ForcedToolChoiceExtractor(model_class=int)  # type: ignore[type-var]

    async def test_rejects_empty_tool_name(self) -> None:
        with self.assertRaisesRegex(TypeError, "tool_name must be"):
            ForcedToolChoiceExtractor(model_class=_UserRecord, tool_name="")


if __name__ == "__main__":
    unittest.main()
