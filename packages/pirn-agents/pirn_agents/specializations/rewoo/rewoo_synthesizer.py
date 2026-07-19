"""``ReWooSynthesizer`` — fold the parallel tool evidence into one final answer.

Algorithm:
    1. Receive the ``goal`` (str), the planned ``plan`` (tuple of
       :class:`ToolCall`), the gathered ``results`` (tuple of
       :class:`ToolResult`), and the ``llm``.
    2. Validate types at process time.
    3. Render an evidence block pairing each planned call with its result.
    4. Ask the LLM once to synthesise the final answer from the evidence.
    5. Return a :class:`ReWooResult` carrying the answer, plan, and results.

Together with :class:`ReWooPlanner` this bounds a ReWOO run to exactly two LLM
round-trips (plan + synthesise) no matter how many tools ran.

References:
    - Xu et al. (2023) "ReWOO" https://arxiv.org/abs/2305.18323
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.rewoo.rewoo_result import ReWooResult
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_result import ToolResult


class ReWooSynthesizer(Knot):
    """Synthesise the final :class:`ReWooResult` from the parallel evidence."""

    def __init__(
        self,
        *,
        goal: Knot | str,
        plan: Knot | Sequence[ToolCall],
        results: Knot | Sequence[ToolResult],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            goal=goal,
            plan=plan,
            results=results,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        goal: str,
        plan: Sequence[ToolCall],
        results: Sequence[ToolResult],
        llm: LLMProvider,
        **_: Any,
    ) -> ReWooResult:
        """Synthesise the final answer and return a typed :class:`ReWooResult`.

        Args:
            goal: The original task.
            plan: The planned tool calls (in order).
            results: The tool results gathered in parallel (in plan order).
            llm: Provider used for the single synthesis round-trip.

        Returns:
            A :class:`ReWooResult` with the answer, plan, and results.

        Raises:
            TypeError: If any input has the wrong type.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ReWooSynthesizer: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(goal, str):
            raise TypeError(f"ReWooSynthesizer: goal must be a string, got {type(goal).__name__}")
        plan_tuple = tuple(plan)
        results_tuple = tuple(results)
        for index, call in enumerate(plan_tuple):
            if not isinstance(call, ToolCall):
                raise TypeError(
                    f"ReWooSynthesizer: plan[{index}] must be a ToolCall, got {type(call).__name__}"
                )
        for index, result in enumerate(results_tuple):
            if not isinstance(result, ToolResult):
                raise TypeError(
                    f"ReWooSynthesizer: results[{index}] must be a ToolResult, got "
                    f"{type(result).__name__}"
                )
        evidence = self._render_evidence(plan_tuple, results_tuple)
        synthesis_system = (
            "You are a solver. Using only the tool evidence below, write the "
            "final answer to the goal. Be concise and do not call any more tools."
        )
        user = f"Goal:\n{goal}\n\nEvidence:\n{evidence}"
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": synthesis_system},
                {"role": "user", "content": user},
            ]
        )
        answer = LlmResponseText().extract(raw)
        return ReWooResult(answer=answer, plan=plan_tuple, results=results_tuple)

    @staticmethod
    def _render_evidence(
        plan: tuple[ToolCall, ...],
        results: tuple[ToolResult, ...],
    ) -> str:
        by_call_id = {result.call_id: result for result in results}
        lines: list[str] = []
        for call in plan:
            result = by_call_id.get(call.call_id)
            value = "<missing>" if result is None else repr(result.result)
            lines.append(f"{call.tool_name}({call.arguments.get('input', '')}) -> {value}")
        return "\n".join(lines)
