"""``CalculatorTool`` — safe arithmetic evaluation as a tool knot.

Wraps :meth:`~pirn_agents.tools.calculator.safe_evaluator.SafeEvaluator.evaluate`
(a zero-dependency, ``ast``-based evaluator that never calls ``eval``/``exec``)
as a :class:`~pirn_agents.tools.tool.Tool`. Invalid or malicious input raises
:class:`ValueError`, which the engine records as the call's ``Err``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.calculator.safe_evaluator import SafeEvaluator
from pirn_agents.tools.tool import Tool


class CalculatorTool(Tool):
    """Evaluate an arithmetic expression (e.g. '2 + 3 * 4', 'sqrt(2)', '(1 + 2) ** 3'). Supports + - * / // % ** and abs/round/min/max/sqrt/floor/ceil with the constants pi, e, tau. No variables, attribute access, or code execution."""

    tool_name: ClassVar[str] = "calculator"

    def __init__(self, *, expression: Knot | str, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(expression=expression, _config=_config, **kwargs)

    async def process(
        self,
        expression: Annotated[str, Field(description="The arithmetic expression to evaluate.")],
        **_: Any,
    ) -> Mapping[str, Any]:
        """Evaluate ``expression`` and return the numeric result.

        Args:
            expression: A non-empty arithmetic expression.

        Returns:
            A mapping ``{"expression": <str>, "result": <number>}``.

        Raises:
            ValueError: If the expression is empty or contains a disallowed
                construct.
            ZeroDivisionError: If the expression divides by zero.
        """
        if not expression:
            raise ValueError("calculator: 'expression' must be a non-empty string")
        value = SafeEvaluator.evaluate(expression)
        return {"expression": expression, "result": value}
