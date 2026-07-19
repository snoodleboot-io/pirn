"""``ReWooPlanner`` — produce the complete tool-call plan up front (no execution).

Algorithm:
    1. Receive the resolved ``goal`` (str), ``llm`` (LLMProvider), and
       ``tool_descriptions`` (str listing the callable tools).
    2. Validate types at process time.
    3. Ask the LLM, in a single call, to emit a numbered plan of independent
       tool calls in the line format ``<n>. <tool_name>: <input>``.
    4. Parse each matching line into a :class:`ToolCall` with a stable
       ``call_id`` (``"c<index>"``) and ``arguments={"input": <input>}``.
    5. Return the ordered tuple of :class:`ToolCall`s.

The planner performs exactly one LLM round-trip regardless of how many tools the
plan contains — the round-trip saving over ReAct, which calls the LLM once per
step.

References:
    - Xu et al. (2023) "ReWOO: Decoupling Reasoning from Observations for
      Efficient Augmented Language Models" https://arxiv.org/abs/2305.18323
"""

from __future__ import annotations

import re
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.types.tool_call import ToolCall


class ReWooPlanner(Knot):
    """Emit the full ordered :class:`ToolCall` plan in a single LLM round-trip."""

    def __init__(
        self,
        *,
        goal: Knot | str,
        llm: Knot | LLMProvider,
        tool_descriptions: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            goal=goal,
            llm=llm,
            tool_descriptions=tool_descriptions,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        goal: str,
        llm: LLMProvider,
        tool_descriptions: str,
        **_: Any,
    ) -> tuple[ToolCall, ...]:
        """Plan every tool call up front and return them in order.

        Args:
            goal: The task the plan should accomplish.
            llm: Provider used for the single planning round-trip.
            tool_descriptions: A newline-listed description of callable tools.

        Returns:
            An ordered tuple of :class:`ToolCall`s, one per parsed plan line.

        Raises:
            TypeError: If ``goal``/``tool_descriptions`` are not strings or
                ``llm`` is not an :class:`LLMProvider`.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"ReWooPlanner: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(goal, str):
            raise TypeError(f"ReWooPlanner: goal must be a string, got {type(goal).__name__}")
        if not isinstance(tool_descriptions, str):
            raise TypeError(
                "ReWooPlanner: tool_descriptions must be a string, got "
                f"{type(tool_descriptions).__name__}"
            )
        planning_system = (
            "You are a planner. Decompose the goal into a numbered list of "
            "independent tool calls that can all run in parallel. Emit each on "
            "its own line as '<n>. <tool_name>: <input>' using only the listed "
            "tools. Do not execute them; only plan."
        )
        user = f"Goal:\n{goal}\n\nAvailable tools:\n{tool_descriptions}"
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": planning_system},
                {"role": "user", "content": user},
            ]
        )
        return self._parse_calls(LlmResponseText().extract(raw))

    @staticmethod
    def _parse_calls(text: str) -> tuple[ToolCall, ...]:
        pattern = re.compile(r"^\s*\d+[.)]\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$")
        calls: list[ToolCall] = []
        for line in text.splitlines():
            match = pattern.match(line)
            if match is None:
                continue
            tool_name = match.group(1)
            argument = match.group(2).strip()
            calls.append(
                ToolCall(
                    tool_name=tool_name,
                    arguments={"input": argument},
                    call_id=f"c{len(calls)}",
                )
            )
        return tuple(calls)
