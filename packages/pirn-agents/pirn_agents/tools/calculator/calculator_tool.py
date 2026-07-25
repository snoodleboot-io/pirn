"""``CalculatorTool`` — safe arithmetic evaluation as a base :class:`Tool`.

Wraps :func:`~pirn_agents.tools.calculator._safe_evaluator.evaluate_expression`
(a zero-dependency, ``ast``-based evaluator that never calls ``eval``/``exec``)
in the F1 :class:`~pirn_agents.tool.Tool` protocol. Invalid or malicious input
raises :class:`ValueError`, which :meth:`~pirn_agents.tools.base_tool.BaseTool.as_tool_result`
surfaces as a structured :attr:`ToolStatus.ERROR` result.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.calculator._safe_evaluator import evaluate_expression


class CalculatorTool(BaseTool):
    """Evaluate arithmetic expressions safely, with no code-execution surface."""

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"calculator"``."""
        return "calculator"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return (
            "Evaluate an arithmetic expression (e.g. '2 + 3 * 4', 'sqrt(2)', "
            "'(1 + 2) ** 3'). Supports + - * / // % ** and abs/round/min/max/"
            "sqrt/floor/ceil with the constants pi, e, tau. No variables, "
            "attribute access, or code execution."
        )

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the single ``expression`` argument."""
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The arithmetic expression to evaluate.",
                }
            },
            "required": ["expression"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Evaluate the ``expression`` argument and return the numeric result.

        Args:
            arguments: Must contain ``"expression"`` (or the generic ``"input"``
                alias) as a non-empty string.

        Returns:
            A mapping ``{"expression": <str>, "result": <number>}``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If the expression is missing/empty or contains a
                disallowed construct.
            ZeroDivisionError: If the expression divides by zero.
        """
        self._require_mapping(self.name, arguments)
        expression = self._string_argument(self.name, arguments, "expression")
        value = evaluate_expression(expression)
        return {"expression": expression, "result": value}
