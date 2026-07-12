"""``ReWooPipeline`` — the decoupled plan / parallel-execute / synthesise ReWOO loop.

A :class:`SubTapestry` that wires, as a static inner tapestry:

1. :class:`ReWooPlanner` — one LLM call emitting the complete tool-call plan.
2. :class:`~pirn_agents.parallel_tool_executor.ParallelToolExecutor` (F1) — runs
   every planned call concurrently under a bounded-concurrency semaphore.
3. :class:`ReWooSynthesizer` — one LLM call folding the gathered evidence into the
   final :class:`ReWooResult`.

Because the plan is produced before any tool runs and the tools run in parallel, a
ReWOO run costs exactly two LLM round-trips regardless of tool count — the latency
and token win over sequential ReAct, which pays one round-trip per step.

Algorithm:
    1. Validate ``goal`` (str), ``llm`` (LLMProvider), ``tools`` (each a Tool),
       and ``max_concurrency`` (>= 1).
    2. Build a :class:`Toolset` and a newline tool-description block.
    3. Wire planner → executor → synthesiser and return the synthesiser sink.

References:
    - Xu et al. (2023) "ReWOO" https://arxiv.org/abs/2305.18323
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.specializations.rewoo.rewoo_planner import ReWooPlanner
from pirn_agents.specializations.rewoo.rewoo_synthesizer import ReWooSynthesizer
from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset


class ReWooPipeline(SubTapestry):
    """Decoupled plan → parallel-execute → synthesise ReWOO agent."""

    def __init__(
        self,
        *,
        goal: Knot | str,
        llm: Knot | LLMProvider,
        tools: Knot | Sequence[Tool],
        max_concurrency: Knot | int = 8,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            goal=goal,
            llm=llm,
            tools=tools,
            max_concurrency=max_concurrency,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        goal: str,
        llm: LLMProvider,
        tools: Sequence[Tool],
        max_concurrency: int = 8,
        **_: Any,
    ) -> Any:
        """Wire the ReWOO inner pipeline and return its synthesiser sink.

        Args:
            goal: The task to solve.
            llm: Provider shared by the planner and synthesiser.
            tools: Tools the plan may call; assembled into a :class:`Toolset`.
            max_concurrency: Bound on simultaneously in-flight tool calls.

        Returns:
            The :class:`ReWooSynthesizer` sink whose output is the
            :class:`ReWooResult`.

        Raises:
            TypeError: If ``llm`` is not an LLMProvider or any tool is not a Tool.
            ValueError: If ``max_concurrency`` is less than 1.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"ReWooPipeline: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(goal, str):
            raise TypeError(f"ReWooPipeline: goal must be a string, got {type(goal).__name__}")
        if not isinstance(max_concurrency, int) or max_concurrency < 1:
            raise ValueError(
                f"ReWooPipeline: max_concurrency must be >= 1, got {max_concurrency!r}"
            )
        tool_tuple = tuple(tools)
        for index, candidate in enumerate(tool_tuple):
            if not isinstance(candidate, Tool):
                raise TypeError(
                    f"ReWooPipeline: tools[{index}] must be a Tool, got {type(candidate).__name__}"
                )
        toolset = Toolset(tool_tuple)
        tool_descriptions = "\n".join(f"- {tool.name}: {tool.description}" for tool in tool_tuple)
        planner = ReWooPlanner(
            goal=goal,
            llm=llm,
            tool_descriptions=tool_descriptions,
            _config=KnotConfig(id="rewoo_plan"),
        )
        executor = ParallelToolExecutor(
            tool_calls=planner,
            toolset=toolset,
            max_concurrency=max_concurrency,
            timeout=None,
            retries=0,
            _config=KnotConfig(id="rewoo_exec", validate_io=False),
        )
        return ReWooSynthesizer(
            goal=goal,
            plan=planner,
            results=executor,
            llm=llm,
            _config=KnotConfig(id="rewoo_synth"),
        )
