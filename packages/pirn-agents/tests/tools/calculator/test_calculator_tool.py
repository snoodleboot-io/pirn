"""Mirrored tests for the calculator tool and its safe evaluator (PIR-159).

Covers valid arithmetic, division-by-zero, the typed F1 result shape, and a
battery of adversarial payloads (``__import__``, attribute traversal, name and
call injection) that must all be rejected as structured errors — never executed.
"""

from __future__ import annotations

import math

import pytest

from pirn_agents.tools.calculator._safe_evaluator import evaluate_expression
from pirn_agents.tools.calculator.calculator_tool import CalculatorTool
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus


class TestSafeEvaluator:
    @pytest.mark.parametrize(
        ("expression", "expected"),
        [
            ("2 + 3", 5),
            ("2 + 3 * 4", 14),
            ("(1 + 2) ** 3", 27),
            ("10 // 3", 3),
            ("10 % 3", 1),
            ("-5 + 2", -3),
            ("+7", 7),
            ("2 ** 0.5", math.sqrt(2)),
            ("abs(-4)", 4),
            ("round(3.14159, 2)", 3.14),
            ("min(3, 7, 1)", 1),
            ("max(3, 7, 1)", 7),
            ("sqrt(16)", 4.0),
            ("floor(3.9)", 3),
            ("ceil(3.1)", 4),
            ("pi", math.pi),
            ("2 * e", 2 * math.e),
        ],
    )
    def test_valid_arithmetic(self, expression: str, expected: float) -> None:
        assert evaluate_expression(expression) == pytest.approx(expected)

    def test_division_by_zero_raises(self) -> None:
        with pytest.raises(ZeroDivisionError):
            evaluate_expression("1 / 0")

    @pytest.mark.parametrize(
        "payload",
        [
            "__import__('os').system('echo pwned')",
            "(1).__class__",
            "().__class__.__bases__",
            "os.getcwd()",
            "open('/etc/passwd')",
            "eval('1+1')",
            "exec('x=1')",
            "lambda: 1",
            "[x for x in range(3)]",
            "{'a': 1}",
            "'string'",
            "1 if True else 2",
            "a + 1",
            "unknown_func(2)",
            "1 & 2",
            "1 << 2",
        ],
    )
    def test_malicious_payloads_rejected(self, payload: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            evaluate_expression(payload)

    def test_exponent_guard_blocks_runaway_power(self) -> None:
        with pytest.raises(ValueError, match="exponent too large"):
            evaluate_expression("9 ** 9999")

    def test_non_string_rejected(self) -> None:
        with pytest.raises(TypeError):
            evaluate_expression(123)  # type: ignore[arg-type]

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError):
            evaluate_expression("   ")

    def test_boolean_literal_rejected(self) -> None:
        with pytest.raises(ValueError):
            evaluate_expression("True + 1")


class TestCalculatorTool:
    def test_schema_shape(self) -> None:
        tool = CalculatorTool()
        assert tool.name == "calculator"
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "expression" in schema["properties"]
        assert schema["required"] == ["expression"]

    async def test_invoke_returns_result_mapping(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"expression": "6 * 7"})
        assert result == {"expression": "6 * 7", "result": 42}

    async def test_invoke_accepts_input_alias(self) -> None:
        tool = CalculatorTool()
        result = await tool.invoke({"input": "1 + 1"})
        assert result["result"] == 2

    async def test_as_tool_result_ok(self) -> None:
        tool = CalculatorTool()
        call = ToolCall(tool_name="calculator", arguments={"expression": "2 + 2"}, call_id="c1")
        outcome = await tool.as_tool_result(call)
        assert outcome.status is ToolStatus.OK
        assert outcome.call_id == "c1"
        assert outcome.result["result"] == 4
        assert outcome.error is None
        assert outcome.latency is not None

    async def test_as_tool_result_error_is_structured(self) -> None:
        tool = CalculatorTool()
        call = ToolCall(
            tool_name="calculator",
            arguments={"expression": "__import__('os')"},
            call_id="c2",
        )
        outcome = await tool.as_tool_result(call)
        assert outcome.status is ToolStatus.ERROR
        assert outcome.result is None
        assert outcome.error is not None

    async def test_as_tool_result_rejects_non_toolcall(self) -> None:
        tool = CalculatorTool()
        with pytest.raises(TypeError):
            await tool.as_tool_result({"arguments": {}})  # type: ignore[arg-type]

    async def test_invoke_rejects_non_mapping(self) -> None:
        tool = CalculatorTool()
        with pytest.raises(TypeError):
            await tool.invoke("2 + 2")  # type: ignore[arg-type]
