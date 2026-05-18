"""Example: Agentic session as a true dynamic DAG.

A single session receives a sequence of messages and works through them
iteratively.  The whole session is ONE extensible run — the graph grows with
each iteration as knots register their successors directly.

Architecture:

    AgentPlanner → action_0, action_1, ... (concurrent)
                 → Aggregator(all actions)
                 → AgentDecider(results=aggregator, ctx=self)

    AgentDecider: integrates results, then either
        → next AgentPlanner(ctx=self)      (more work to do)
        → _SessionFinalizer(state=self)    (session complete)

Every knot is a direct node in a single extensible tapestry run.  Data flows
through real parent edges — there is no shared mutable state blob.

Action types:
- ``tool_call``  — local function (weather, calculator)
- ``mcp_call``   — simulated remote service (web search, knowledge base)
- ``subagent``   — inner tapestry with its own two-step pipeline

Run with:
    uv run python examples/llm_agent/agent_loop.py
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import re
from dataclasses import dataclass, replace
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry, get_current_store

MAX_ITERATIONS_PER_MSG = 4
MAX_TOTAL_ITERATIONS = 20
SESSION_COMPLETE_ID = "session_complete"


# ----------------------------------------------------------------- state models


@dataclass(frozen=True)
class StepResult:
    iteration: int
    msg_idx: int
    action_type: str  # "tool_call" | "mcp_call" | "subagent"
    name: str
    output: str


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

    def evolve(self, **changes) -> SessionContext:
        return replace(self, **changes)


@dataclass
class PlannedAction:
    action_type: str  # "tool_call" | "mcp_call" | "subagent"
    name: str
    args: dict


# ----------------------------------------------------------------- fake back-ends


def _rng(ctx: SessionContext, extra: str = "") -> random.Random:
    """Deterministic RNG seeded from current message + run_seed + iteration."""
    key = f"{ctx.current_message}|{ctx.run_seed}|{ctx.iteration}|{extra}"
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _fake_tool(name: str, args: dict, rng: random.Random) -> str:
    if name == "get_weather":
        loc = args.get("location", "unknown")
        temp = rng.randint(8, 28)
        cond = rng.choice(["Clear", "Overcast", "Light rain", "Sunny", "Windy"])
        return f"{loc}: {cond}, {temp}°C"
    if name == "calculate":
        expr = args.get("expression", "0")
        try:
            return f"{expr} = {eval(expr, {'__builtins__': {}})}"
        except Exception:
            return f"could not evaluate: {expr}"
    if name == "read_file":
        n = rng.randint(1, 9)
        return f"[contents of {args.get('path', '?')}]: lorem ipsum policy text paragraph {n}"
    return f"[tool:{name}] ok"


def _fake_mcp(name: str, args: dict, rng: random.Random) -> str:
    if name == "web_search":
        q = args.get("query", "")
        snippets = [
            f"Recent study on '{q}' shows promising results in Q{rng.randint(1, 4)} 2025.",
            f"Experts disagree on {q}; {rng.randint(2, 8)} competing frameworks proposed.",
            f"'{q}' trend up {rng.randint(10, 80)}% year-over-year according to new data.",
        ]
        return rng.choice(snippets)
    if name == "kb_search":
        topics = {
            "refund": "Refunds issued within 30 days. Digital goods non-refundable post-download.",
            "cancellation": "Cancel anytime; access continues to end of billing period.",
            "pricing": "Basic $9/mo · Pro $29/mo · Enterprise $99/mo.",
        }
        q = args.get("query", "").lower()
        for k, v in topics.items():
            if k in q:
                return v
        return "No matching article found."
    if name == "fetch_url":
        words = rng.randint(200, 800)
        return f"[page content from {args.get('url', '?')}]: retrieved {words} words"
    return f"[mcp:{name}] ok"


def _fake_subagent(name: str, args: dict, context: str, rng: random.Random) -> str:
    if name == "summarise":
        words = rng.randint(40, 120)
        pts = rng.randint(2, 5)
        return f"Summary ({words} words): {context[:80]}… Key points: {pts} identified."
    if name == "draft_email":
        tone = rng.choice(["professional", "empathetic", "concise"])
        return f"[{tone} email draft] Dear customer, regarding your request: {context[:60]}…"
    if name == "analyse":
        n = rng.randint(2, 6)
        return f"Analysis complete. {n} factors identified from: {context[:60]}…"
    return f"[subagent:{name}] processed: {context[:50]}"


# ----------------------------------------------------------------- planner


def plan_next_actions(ctx: SessionContext) -> list[PlannedAction]:
    """Plan the next actions for the current message.

    Seeds the RNG from (current_message, run_seed, iteration) so the same
    message with a different seed produces a different action mix.  Later
    iterations lean toward synthesis; earlier ones gather data in parallel.
    """
    rng = _rng(ctx, extra="plan")
    task = ctx.current_message.lower()
    msg_steps = [s for s in ctx.scratchpad if s.msg_idx == ctx.msg_idx]

    if msg_steps and ctx.msg_iteration >= 2:
        if rng.random() < 0.6 or ctx.msg_iteration >= MAX_ITERATIONS_PER_MSG - 1:
            context = " | ".join(s.output for s in msg_steps[-3:])
            return [PlannedAction("subagent", "summarise", {"context": context})]

    actions: list[PlannedAction] = []

    if "weather" in task:
        locs = ["London", "Tokyo", "New York", "Paris", "Berlin"]
        n_locs = rng.randint(1, min(3, 1 + ctx.msg_iteration))
        chosen = rng.sample(locs, n_locs)
        actions += [PlannedAction("tool_call", "get_weather", {"location": loc}) for loc in chosen]

    if any(w in task for w in ["calculat", "percent", "interest", "cost"]):
        expr = rng.choice(["150 * 1.2", "5000 * 0.035 * 10", "280 * 0.15", "99 * 12"])
        actions.append(PlannedAction("tool_call", "calculate", {"expression": expr}))

    if any(w in task for w in ["research", "find", "look up", "search"]):
        mcp_name = rng.choice(["web_search", "kb_search"])
        actions.append(PlannedAction("mcp_call", mcp_name, {"query": task[:60]}))

    if any(w in task for w in ["policy", "refund", "cancel", "plan"]):
        actions.append(PlannedAction("mcp_call", "kb_search", {"query": task[:50]}))

    if any(w in task for w in ["write", "draft", "email", "report", "summarise", "summary"]):
        context = " | ".join(s.output for s in msg_steps) or task
        sub_name = rng.choice(["summarise", "draft_email", "analyse"])
        actions.append(PlannedAction("subagent", sub_name, {"context": context[:200]}))

    if any(w in task for w in ["url", "page", "fetch", "scrape"]):
        actions.append(PlannedAction("mcp_call", "fetch_url", {"url": "https://example.com"}))

    if not actions:
        actions.append(
            rng.choice(
                [
                    PlannedAction("mcp_call", "web_search", {"query": task[:60]}),
                    PlannedAction("tool_call", "get_weather", {"location": "London"}),
                    PlannedAction("subagent", "analyse", {"context": task}),
                ]
            )
        )

    msg_types = {s.action_type for s in msg_steps}
    if rng.random() < 0.35 and len(actions) < 4 and "subagent" not in msg_types:
        actions.append(
            rng.choice(
                [
                    PlannedAction("mcp_call", "web_search", {"query": f"{task[:30]} latest"}),
                    PlannedAction("tool_call", "calculate", {"expression": "100 * 1.035 ** 5"}),
                ]
            )
        )

    return actions


# ----------------------------------------------------------------- action knots


@knot
async def run_tool_call(action: PlannedAction, ctx: SessionContext, **_) -> StepResult:
    """Execute a local tool function."""
    rng = _rng(ctx, extra=action.name)
    output = _fake_tool(action.name, action.args, rng)
    return StepResult(
        iteration=ctx.iteration,
        msg_idx=ctx.msg_idx,
        action_type="tool_call",
        name=action.name,
        output=output,
    )


@knot
async def run_mcp_call(action: PlannedAction, ctx: SessionContext, **_) -> StepResult:
    """Execute a remote MCP service call (simulated)."""
    await asyncio.sleep(0)
    rng = _rng(ctx, extra=action.name)
    output = _fake_mcp(action.name, action.args, rng)
    return StepResult(
        iteration=ctx.iteration,
        msg_idx=ctx.msg_idx,
        action_type="mcp_call",
        name=action.name,
        output=output,
    )


class SubAgentRunner(SubTapestry):
    """Run a sub-agent as its own inner tapestry (prepare_context → execute_subagent)."""

    async def process(self, action: PlannedAction, ctx: SessionContext, **_) -> Knot:  # type: ignore[override]
        rng = _rng(ctx, extra=action.name)
        context = action.args.get("context", ctx.current_message)

        @knot
        async def prepare_context(raw: str, **__) -> str:
            return raw[:300].strip()

        @knot
        async def execute_subagent(prepared: str, **__) -> StepResult:
            raw_output = _fake_subagent(action.name, action.args, prepared, rng)
            return StepResult(
                iteration=ctx.iteration,
                msg_idx=ctx.msg_idx,
                action_type="subagent",
                name=action.name,
                output=raw_output,
            )

        with Tapestry() as inner:
            raw_p = Parameter("raw", str, default=context, _config=KnotConfig(id="context_input"))
            ctx_knot = prepare_context(raw=raw_p, _config=KnotConfig(id="prepare"))
            sink = execute_subagent(prepared=ctx_knot, _config=KnotConfig(id="subagent_output"))

        return sink


# ----------------------------------------------------------------- planner knot


class AgentPlanner(Knot):
    """Plans the next set of actions and registers them directly into the running tapestry.

    Outputs the updated context (with bumped iteration counters) so that action
    knots wired to ``ctx=self`` receive it as a data input.
    """

    async def process(self, ctx: SessionContext, **_) -> SessionContext:  # type: ignore[override]
        new_ctx = ctx.evolve(iteration=ctx.iteration + 1, msg_iteration=ctx.msg_iteration + 1)
        actions = plan_next_actions(new_ctx)

        store = get_current_store()
        if store is None:
            return new_ctx

        prefix = self.knot_id
        action_knots: dict[str, Knot] = {}

        for i, action in enumerate(actions):
            node_id = f"{prefix}__act_{i}"
            if action.action_type == "tool_call":
                ak: Knot = run_tool_call(
                    action=action, ctx=self, _config=KnotConfig(id=node_id, validate_io=False)
                )
            elif action.action_type == "mcp_call":
                ak = run_mcp_call(
                    action=action, ctx=self, _config=KnotConfig(id=node_id, validate_io=False)
                )
            else:
                ak = SubAgentRunner(
                    action=action, ctx=self, _config=KnotConfig(id=node_id, validate_io=False)
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
    """Integrates action results, updates context, and spawns the next planner or terminal.

    ``results`` arrives from the aggregator (a real data edge).
    ``ctx`` arrives from the planner that spawned this decider (a real data edge).
    """

    async def process(self, results: list[StepResult], ctx: SessionContext, **_) -> SessionContext:  # type: ignore[override]
        new_scratchpad = ctx.scratchpad + tuple(results)
        new_ctx = ctx.evolve(scratchpad=new_scratchpad)

        # Resolved when a synthesis subagent ran.
        if results and results[-1].action_type == "subagent":
            new_ctx = new_ctx.evolve(
                responses=(*new_ctx.responses, results[-1].output),
                msg_idx=new_ctx.msg_idx + 1,
                msg_iteration=0,
            )
        else:
            rng = _rng(new_ctx, extra="termination")
            msg_steps = [s for s in new_scratchpad if s.msg_idx == new_ctx.msg_idx]
            if len(msg_steps) >= 2 and rng.random() < 0.5:
                ctx_str = " | ".join(s.output for s in msg_steps[-3:])
                new_ctx = new_ctx.evolve(
                    responses=(
                        *new_ctx.responses,
                        f"Resolved after {new_ctx.msg_iteration} iterations: {ctx_str[:120]}",
                    ),
                    msg_idx=new_ctx.msg_idx + 1,
                    msg_iteration=0,
                )

        store = get_current_store()
        if store is None:
            return new_ctx

        if not new_ctx.done and new_ctx.iteration < MAX_TOTAL_ITERATIONS:
            next_id = _planner_id(new_ctx)
            store.register(
                AgentPlanner(ctx=self, _config=KnotConfig(id=next_id, validate_io=False))
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
    """Terminal knot — surfaces the final session context as the run output."""

    async def process(self, state: SessionContext, **_) -> SessionContext:  # type: ignore[override]
        return state


# ----------------------------------------------------------------- tapestry


def build_tapestry(*, initial_ctx: SessionContext | None = None, history=None) -> Tapestry:
    t = Tapestry(history=history)
    seed_ctx = initial_ctx or make_session()
    first_planner = AgentPlanner(
        ctx=seed_ctx, _config=KnotConfig(id=_planner_id(seed_ctx), validate_io=False)
    )
    t.store.register(first_planner)
    return t


# ----------------------------------------------------------------- conversation


MESSAGES = [
    "What's the weather forecast for my trip to London and Tokyo?",
    "Calculate the compound interest on £5000 at 3.5% for 10 years",
    "Research the latest developments in quantum computing and summarise for me",
    "Find our cancellation policy and draft a customer email explaining it",
    "I need a cost analysis for our Pro plan renewals this quarter",
    "What's the weather in New York and write a brief travel advisory",
]


def _planner_id(ctx: SessionContext) -> str:
    """Short human-readable ID for an AgentPlanner from message content + position."""
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

    _TYPE_ICON = {"tool_call": "⚙", "mcp_call": "🌐", "subagent": "🤖"}

    print("\n── Agent session ──\n")

    result = await t.run(extensible=True)

    if not result.succeeded:
        exc = result.exceptions[0] if result.exceptions else None
        print(f"FAILED: {exc.knot_id if exc else '?'}: {exc.message[:80] if exc else ''}")
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
        print(f"     {steps_summary}")
        print(f"     → {response[:100]}")
        print()

    history.close()


if __name__ == "__main__":
    asyncio.run(main())
