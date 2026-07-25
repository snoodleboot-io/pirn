"""Unit tests for :class:`ArgumentValidator`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn_agents.tool import Tool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus
from pirn_agents.validation.argument_validator import ArgumentValidator


class StubTool(Tool):
    """Tool with a real schema (required int ``x``, optional str ``y``).

    Tracks whether :meth:`invoke` was called so tests can assert that an
    invalid call never reaches the tool.
    """

    def __init__(self, additional_properties: bool | None = None) -> None:
        self.invoked: bool = False
        self._additional_properties = additional_properties

    @property
    def name(self) -> str:
        return "stub"

    @property
    def description(self) -> str:
        return "A stub tool for validation tests."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "string"},
            },
            "required": ["x"],
        }
        if self._additional_properties is not None:
            schema["additionalProperties"] = self._additional_properties
        return schema

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        self.invoked = True
        return arguments


def _call(arguments: Mapping[str, Any]) -> ToolCall:
    return ToolCall(tool_name="stub", arguments=arguments, call_id="c1")


class TestArgumentValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ArgumentValidator()

    def test_valid_args_return_none(self) -> None:
        result = self.validator.validate(_call({"x": 1, "y": "hi"}), StubTool())
        assert result is None

    def test_valid_args_without_optional_return_none(self) -> None:
        result = self.validator.validate(_call({"x": 1}), StubTool())
        assert result is None

    def test_missing_required_is_error_and_tool_not_invoked(self) -> None:
        tool = StubTool()
        result = self.validator.validate(_call({"y": "hi"}), tool)
        assert result is not None
        assert result.status is ToolStatus.ERROR
        assert result.call_id == "c1"
        assert result.error is not None
        assert "x" in result.error
        assert "missing_required" in result.error
        assert tool.invoked is False

    def test_wrong_type_is_error_with_expected_integer(self) -> None:
        tool = StubTool()
        result = self.validator.validate(_call({"x": "notint"}), tool)
        assert result is not None
        assert result.status is ToolStatus.ERROR
        assert result.error is not None
        assert "expected:integer" in result.error
        assert "got:str" in result.error
        assert tool.invoked is False

    def test_bool_rejected_for_integer(self) -> None:
        result = self.validator.validate(_call({"x": True}), StubTool())
        assert result is not None
        assert result.error is not None
        assert "expected:integer" in result.error

    def test_optional_arg_present_and_correct_returns_none(self) -> None:
        result = self.validator.validate(_call({"x": 1, "y": "ok"}), StubTool())
        assert result is None

    def test_optional_arg_wrong_type_is_error(self) -> None:
        result = self.validator.validate(_call({"x": 1, "y": 5}), StubTool())
        assert result is not None
        assert result.error is not None
        assert "expected:string" in result.error
        assert "got:int" in result.error

    def test_extra_arg_permitted_by_default(self) -> None:
        result = self.validator.validate(_call({"x": 1, "z": "extra"}), StubTool())
        assert result is None

    def test_extra_arg_rejected_when_additional_properties_false(self) -> None:
        tool = StubTool(additional_properties=False)
        result = self.validator.validate(_call({"x": 1, "z": "extra"}), tool)
        assert result is not None
        assert result.status is ToolStatus.ERROR
        assert result.error is not None
        assert "z" in result.error
        assert "unexpected_property" in result.error

    def test_extra_arg_allowed_when_additional_properties_true(self) -> None:
        tool = StubTool(additional_properties=True)
        result = self.validator.validate(_call({"x": 1, "z": "extra"}), tool)
        assert result is None
