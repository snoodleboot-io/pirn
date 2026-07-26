"""Unit tests for :class:`ForcedToolChoiceStrategy`."""

from __future__ import annotations

import unittest

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.forced_tool_choice_strategy import (
    ForcedToolChoiceStrategy,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from tests.specializations.structured_output.structured_stubs import (
    StubStructuredProvider,
    tool_call_response,
)


class _UserRecord(BaseModel):
    name: str
    age: int


def _strategy() -> ForcedToolChoiceStrategy:
    return ForcedToolChoiceStrategy(model_class=_UserRecord, tool_name="extract")


class TestForcedToolChoiceStrategy(unittest.IsolatedAsyncioTestCase):
    def test_is_advertised_reads_forced_tool_choice_flag(self) -> None:
        strategy = _strategy()

        assert strategy.is_advertised(StructuredOutputCapability(forced_tool_choice=True))
        assert not strategy.is_advertised(StructuredOutputCapability(native_schema=True))

    async def test_try_decode_validates_forced_tool_arguments(self) -> None:
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(forced_tool_choice=True),
            structured_response=tool_call_response({"name": "Grace", "age": 45}),
        )

        instance = await _strategy().try_decode(prompt="extract", provider=provider)

        assert isinstance(instance, _UserRecord)
        assert instance.name == "Grace"
        assert "tool_choice" in provider.structured_calls[0]["request_options"]


if __name__ == "__main__":
    unittest.main()
