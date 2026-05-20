"""Example: Agent session v2 — dynamic DAG backed by pirn.domains.agents.

Identical extensible-tapestry architecture as agent_loop.py: a single
extensible run grows with each iteration as knots register their successors.

The difference from v1 is that every **action knot** is a real
``pirn.domains.agents`` composite instead of an ad-hoc helper:

  llm_task   — ContextBuilder → LLMCall → OutputParser
  react      — ReActLoop (Reason+Act loop, 3 iterations)
  planner    — ContextBuilder → Planner → ToolRouter → ToolExecutor

All three return an ``AgentResponse`` so the aggregator sees a uniform type.

``StubLLMProvider`` and ``StubTool`` (concrete implementations of the abstract
interfaces) are defined inline.  Swap them for a real provider by implementing
``LLMProvider.chat`` against your vendor SDK.

Architecture (identical to agent_loop.py):
    AgentPlanner ──► action_0, action_1, ... (concurrent)
                 ──► Aggregator(all actions)
                 ──► AgentDecider(results=aggregator, ctx=self)

    AgentDecider: integrates results, then either
        ──► next AgentPlanner(ctx=self)      (more work to do)
        ──► _SessionFinalizer(state=self)    (session complete)

Run with:
    uv run python examples/llm_agent/agent_loop_v2.py
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.agents.generation.llm_call import LLMCall
from pirn.domains.agents.generation.output_parser import OutputParser
from pirn.domains.agents.input.context_builder import ContextBuilder
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.planning.planner import Planner
from pirn.domains.agents.planning.tool_executor import ToolExecutor
from pirn.domains.agents.planning.tool_router import ToolRouter
from pirn.domains.agents.specializations.react.react_loop import ReActLoop
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry, get_current_store

MAX_ITERATIONS_PER_MSG = 4
MAX_TOTAL_ITERATIONS = 20
SESSION_COMPLETE_ID = "session_complete"


# ----------------------------------------------------------------- stub doubles


class StubLLMProvider(LLMProvider):
    """Scripted LLM double — deterministic, no network required.

    Responses cycle through a fixed pool keyed by the last user message
    so the output is always the same given the same input.
    """

    _POOL: tuple[str, ...] = (
        "I have gathered the relevant information and can now summarise: "
        "the data indicates a clear trend over the past quarter.",
        "After reasoning through the available context I conclude that "
        "the best course of action is to proceed with the staged rollout.",
        "Final Answer: Based on the evidence gathered the primary "
        "finding is a 12% improvement in throughput after the change.",
        "The analysis is complete. Three key factors emerge: latency, "
        "throughput, and error rate — all improved post-deployment.",
        "Research complete. The topic has been investigated across "
        "five sources; consensus points to option B as the stronger "
        "approach given the current constraints.",
    )

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        last = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        idx = int(hashlib.md5(f"{last}{self._seed}".encode()).hexdigest(), 16)
        text = self._POOL[idx % len(self._POOL)]
        return {"role": "assistant", "content": text}

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        resp = await self.chat(messages)

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            yield {"content": resp["content"]}

        return _aiter()

    async def close(self) -> None:
        return None


class StubTool(Tool):
    """Deterministic tool double that returns canned output."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        result_template: str,
    ) -> None:
        self._name = name
        self._description = description
        self._template = result_template

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {"input": {"type": "string"}}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        arg = next(iter(arguments.values()), "") if arguments else ""
        return self._template.format(arg=arg)


# ----------------------------------------------------------------- shared tools / LLM


class PlannerStubLLMProvider(StubLLMProvider):
    """LLM stub for the Planner knot.

    Emits numbered steps that begin with a tool name so ``ToolRouter``
    can match them via substring search.  Lines not starting with ``#``
    become plan steps in ``Planner``.
    """

    _POOL: tuple[str, ...] = (
        "1. calculate: compound interest on the principal amount\n"
        "2. lookup: applicable policy terms and conditions",
        "1. search: recent developments and key findings\n2. calculate: estimated impact figures",
        "1. lookup: existing knowledge base entries\n2. search: supplementary external sources",
        "1. calculate: cost projections for the period\n2. lookup: pricing and billing details",
        "1. search: authoritative references on the topic\n"
        "2. lookup: internal policy documentation",
    )


_LLM = StubLLMProvider(seed=42)
_PLANNER_LLM = PlannerStubLLMProvider(seed=0)

_SEARCH_TOOL = StubTool(
    name="search",
    description="Search for information on a topic.",
    result_template="Search result for '{arg}': found 3 relevant documents "
    "covering historical context, current status, and future outlook.",
)
_CALCULATE_TOOL = StubTool(
    name="calculate",
    description="Evaluate a mathematical expression.",
    result_template="calculate({arg}) = 6125.00",
)
_LOOKUP_TOOL = StubTool(
    name="lookup",
    description="Look up a fact in the knowledge base.",
    result_template="lookup('{arg}'): policy states standard 30-day processing "
    "window; exceptions require manager approval.",
)

_ALL_TOOLS: tuple[Tool, ...] = (_SEARCH_TOOL, _CALCULATE_TOOL, _LOOKUP_TOOL)


# ----------------------------------------------------------------- state models


@dataclass(frozen=True)
class StepResult:
    iteration: int
    msg_idx: int
    action_type: str  # "llm_task" | "react" | "planner"
    name: str
    response: AgentResponse


@dataclass(frozen=True)
class SessionContext:
    messages: tuple[str, ...]
    run_seed: int
    msg_idx: int = 0
    msg_iteration: int = 0
    iteration: int = 0
    scratchpad: tuple[StepResult, ...] = ()
    responses: tuple[str, ...] = ()

    @property
    def current_message(self) -> str:
        return self.messages[self.msg_idx]

    @property
    def done(self) -> bool:
        return self.msg_idx >= len(self.messages)

    def evolve(self, **changes: Any) -> SessionContext:
        return replace(self, **changes)


@dataclass
class PlannedAction:
    action_type: str  # "llm_task" | "react" | "planner"
    name: str


# ----------------------------------------------------------------- planning logic


def _rng(ctx: SessionContext, extra: str = "") -> random.Random:
    key = f"{ctx.current_message}|{ctx.run_seed}|{ctx.iteration}|{extra}"
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def plan_next_actions(ctx: SessionContext) -> list[PlannedAction]:
    """Pick action types for this iteration.

    Later iterations lean toward synthesis (llm_task); early iterations
    prefer data-gathering (react/planner).
    """
    rng = _rng(ctx, extra="plan")
    task = ctx.current_message.lower()
    msg_steps = [s for s in ctx.scratchpad if s.msg_idx == ctx.msg_idx]

    if msg_steps and ctx.msg_iteration >= 2:
        if rng.random() < 0.6 or ctx.msg_iteration >= MAX_ITERATIONS_PER_MSG - 1:
            return [PlannedAction("llm_task", "synthesise")]

    actions: list[PlannedAction] = []

    if any(w in task for w in ["research", "find", "search", "explain", "quantum"]):
        actions.append(PlannedAction("react", "research"))

    if any(w in task for w in ["calculat", "percent", "interest", "cost", "plan"]):
        actions.append(PlannedAction("planner", "compute"))

    if any(w in task for w in ["write", "draft", "email", "report", "summarise", "summary"]):
        actions.append(PlannedAction("llm_task", "draft"))

    if any(w in task for w in ["weather", "forecast", "advisory"]):
        actions.append(PlannedAction("react", "weather_lookup"))

    if any(w in task for w in ["policy", "refund", "cancel", "lookup"]):
        actions.append(PlannedAction("planner", "policy_lookup"))

    if not actions:
        actions.append(
            rng.choice(
                [
                    PlannedAction("react", "explore"),
                    PlannedAction("llm_task", "analyse"),
                    PlannedAction("planner", "investigate"),
                ]
            )
        )

    if rng.random() < 0.25 and len(actions) < 3:
        actions.append(PlannedAction("llm_task", "context_build"))

    return actions


# ----------------------------------------------------------------- action SubTapestries


def _seed_messages(ctx: SessionContext, system: str) -> tuple[AgentMessage, ...]:
    prior = " | ".join(s.response.content[:60] for s in ctx.scratchpad[-3:])
    user_content = ctx.current_message
    if prior:
        user_content = f"{user_content}\n\nPrior findings: {prior}"
    return (
        AgentMessage(role="system", content=system),
        AgentMessage(role="user", content=user_content),
    )


class LLMTaskRunner(SubTapestry):
    """ContextBuilder → LLMCall → OutputParser inner pipeline."""

    async def process(self, ctx: SessionContext, action: PlannedAction, **_: Any) -> Knot:
        msgs = _seed_messages(
            ctx,
            system="You are a helpful assistant. Answer the user's question clearly and concisely.",
        )
        msgs_param = Parameter(
            "messages",
            tuple,
            default=msgs,
            _config=KnotConfig(id="msgs"),
        )
        context_k = ContextBuilder(messages=msgs_param, _config=KnotConfig(id="ctx"))
        llm_k = LLMCall(context=context_k, llm=_LLM, _config=KnotConfig(id="call"))
        return OutputParser(response=llm_k, _config=KnotConfig(id="out"))


class ReActRunner(SubTapestry):
    """ReActLoop inner pipeline — reason + act with stub tools."""

    async def process(self, ctx: SessionContext, action: PlannedAction, **_: Any) -> Knot:
        msgs = _seed_messages(
            ctx,
            system=(
                "You are a research assistant. Use the search, calculate, or lookup tools "
                "as needed. When you have enough information emit: Final Answer: <text>"
            ),
        )
        return ReActLoop(
            messages=list(msgs),
            llm=_LLM,
            tools=list(_ALL_TOOLS),
            max_iterations=3,
            _config=KnotConfig(id="react_loop"),
        )


class _PlanFirstStep(Knot):
    """Extract the first step string from a ``Plan`` for ``ToolRouter``."""

    async def process(self, plan: Any, **_: Any) -> str:
        from pirn.domains.agents.types.plan import Plan as _Plan

        if isinstance(plan, _Plan) and plan.steps:
            return plan.steps[0]
        return str(plan)


class _ToolResultWrapper(Knot):
    """Convert a ToolResult to an AgentResponse for the outer aggregator."""

    async def process(self, exec_out: Any, **_: Any) -> AgentResponse:
        tool_content = (
            str(exec_out.result)
            if exec_out and exec_out.error is None
            else (str(exec_out.error) if exec_out else "[planner: no output]")
        )
        return AgentResponse(content=f"[plan→tool] {tool_content}")


class PlannerRunner(SubTapestry):
    """ContextBuilder → Planner → PlanFirstStep → ToolRouter → ToolExecutor.

    ``_PLANNER_LLM`` is scripted to emit steps containing tool names so
    ``ToolRouter`` can match them.  ``_PlanFirstStep`` extracts the first
    step string from the ``Plan`` before passing it to ``ToolRouter``.
    """

    async def process(self, ctx: SessionContext, action: PlannedAction, **_: Any) -> Knot:
        msgs = _seed_messages(
            ctx,
            system=(
                "You are a planning assistant. Produce a numbered list of steps. "
                "Each step must start with a tool name (search, calculate, or lookup) "
                "followed by a colon and a description. One step per line."
            ),
        )
        msgs_param = Parameter(
            "messages",
            tuple,
            default=msgs,
            _config=KnotConfig(id="msgs"),
        )
        context_k = ContextBuilder(messages=msgs_param, _config=KnotConfig(id="ctx"))
        plan_k = Planner(context=context_k, llm=_PLANNER_LLM, _config=KnotConfig(id="plan"))
        step_k = _PlanFirstStep(plan=plan_k, _config=KnotConfig(id="step"))
        router_k = ToolRouter(
            step=step_k,
            tools=list(_ALL_TOOLS),
            _config=KnotConfig(id="route"),
        )
        exec_k = ToolExecutor(
            call=router_k,
            tools=list(_ALL_TOOLS),
            _config=KnotConfig(id="exec"),
        )
        return _ToolResultWrapper(exec_out=exec_k, _config=KnotConfig(id="out"))


# ----------------------------------------------------------------- planner knot


class AgentPlanner(Knot):
    """Plans next actions and registers the appropriate agent knots.

    Each action becomes a real ``pirn.domains.agents`` SubTapestry:
    ``LLMTaskRunner``, ``ReActRunner``, or ``PlannerRunner``.
    """

    async def process(self, ctx: SessionContext, **_: Any) -> SessionContext:
        new_ctx = ctx.evolve(iteration=ctx.iteration + 1, msg_iteration=ctx.msg_iteration + 1)
        actions = plan_next_actions(new_ctx)

        store = get_current_store()
        if store is None:
            return new_ctx

        prefix = self.knot_id
        action_knots: dict[str, Knot] = {}

        for i, action in enumerate(actions):
            node_id = f"{prefix}__act_{i}"
            if action.action_type == "react":
                ak: Knot = ReActRunner(
                    ctx=self,
                    action=action,
                    _config=KnotConfig(id=node_id, validate_io=False),
                )
            elif action.action_type == "planner":
                ak = PlannerRunner(
                    ctx=self,
                    action=action,
                    _config=KnotConfig(id=node_id, validate_io=False),
                )
            else:
                ak = LLMTaskRunner(
                    ctx=self,
                    action=action,
                    _config=KnotConfig(id=node_id, validate_io=False),
                )
            store.register(ak)
            action_knots[f"r{i}"] = ak

        agg = Aggregator(
            combine=lambda **kw: list(kw.values()),
            _config=KnotConfig(id=f"{prefix}__agg", validate_io=False),
            **action_knots,
        )
        store.register(agg)

        decider = AgentDecider(
            results=agg,
            ctx=self,
            _config=KnotConfig(id=f"{prefix}__decide", validate_io=False),
        )
        store.register(decider)

        return new_ctx


# ----------------------------------------------------------------- decider knot


class AgentDecider(Knot):
    """Integrates AgentResponse results and spawns the next planner or finaliser."""

    async def process(
        self,
        results: list[AgentResponse],
        ctx: SessionContext,
        **_: Any,
    ) -> SessionContext:
        step_results = tuple(
            StepResult(
                iteration=ctx.iteration,
                msg_idx=ctx.msg_idx,
                action_type="agent",
                name=f"step_{j}",
                response=r,
            )
            for j, r in enumerate(results)
            if isinstance(r, AgentResponse)
        )
        new_ctx = ctx.evolve(scratchpad=ctx.scratchpad + step_results)

        rng = _rng(new_ctx, extra="termination")
        msg_steps = [s for s in new_ctx.scratchpad if s.msg_idx == new_ctx.msg_idx]

        synthesised = any(
            "Final Answer" in s.response.content or "synthesise" in s.response.content
            for s in step_results
        )
        enough = len(msg_steps) >= 2 and rng.random() < 0.55

        if synthesised or enough or new_ctx.msg_iteration >= MAX_ITERATIONS_PER_MSG:
            best = max(step_results, key=lambda s: len(s.response.content), default=None)
            summary = best.response.content[:120] if best else "Completed."
            new_ctx = new_ctx.evolve(
                responses=(*new_ctx.responses, summary),
                msg_idx=new_ctx.msg_idx + 1,
                msg_iteration=0,
            )

        store = get_current_store()
        if store is None:
            return new_ctx

        if not new_ctx.done and new_ctx.iteration < MAX_TOTAL_ITERATIONS:
            store.register(
                AgentPlanner(
                    ctx=self,
                    _config=KnotConfig(id=_planner_id(new_ctx), validate_io=False),
                )
            )
        else:
            store.register(
                _SessionFinalizer(
                    state=self,
                    _config=KnotConfig(id=SESSION_COMPLETE_ID, validate_io=False),
                )
            )

        return new_ctx


class _SessionFinalizer(Knot):
    """Terminal knot — surfaces the final SessionContext as the run output."""

    async def process(self, state: SessionContext, **_: Any) -> SessionContext:
        return state


# ----------------------------------------------------------------- tapestry


def build_tapestry(*, initial_ctx: SessionContext | None = None, history=None) -> Tapestry:
    t = Tapestry(history=history)
    seed_ctx = initial_ctx or make_session()
    t.store.register(
        AgentPlanner(
            ctx=seed_ctx,
            _config=KnotConfig(id=_planner_id(seed_ctx), validate_io=False),
        )
    )
    return t


# ----------------------------------------------------------------- conversation


MESSAGES = [
    "Research the latest developments in quantum computing and summarise",
    "Calculate compound interest on £5000 at 3.5% for 10 years",
    "Find our cancellation policy and draft a customer email explaining it",
    "Write a brief analysis of the weather patterns for our travel advisory",
    "I need a cost plan for our Pro tier renewals this quarter",
    "Summarise the key findings from the research into energy storage",
]


def _planner_id(ctx: SessionContext) -> str:
    words = re.sub(r"[^a-z0-9\s]", "", ctx.current_message.lower()).split()[:3]
    slug = "_".join(words)
    return f"{slug}__m{ctx.msg_idx + 1}i{ctx.msg_iteration + 1}"


def make_session(run_seed: int = 1) -> SessionContext:
    return SessionContext(messages=tuple(MESSAGES), run_seed=run_seed)


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    ctx = make_session(run_seed=random.randint(1, 2**31))
    t = build_tapestry(initial_ctx=ctx, history=history)

    _TYPE_ICON = {"llm_task": "💬", "react": "🔄", "planner": "📋", "agent": "🤖"}

    print("\n── Agent session v2 (pirn.domains.agents) ──\n")

    result = await t.run(extensible=True)

    if not result.succeeded:
        exc = result.exceptions[0] if result.exceptions else None
        print(f"FAILED: {exc.knot_id if exc else '?'}: {exc.message[:120] if exc else ''}")
        history.close()
        return

    final: SessionContext = result.outputs[SESSION_COMPLETE_ID]
    print(f"{len(final.messages)} messages · {final.iteration} total iterations\n")

    for i, (msg, response) in enumerate(zip(final.messages, final.responses, strict=True)):
        msg_steps = [s for s in final.scratchpad if s.msg_idx == i]
        steps_summary = "  ".join(
            f"{_TYPE_ICON.get(s.action_type, '·')}{s.name}" for s in msg_steps
        )
        print(f"[{i + 1}] {msg[:70]}")
        if steps_summary:
            print(f"     {steps_summary}")
        print(f"     → {response[:100]}")
        print()

    history.close()


if __name__ == "__main__":
    asyncio.run(main())
