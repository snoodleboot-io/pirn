"""Example: Agentic loop with dynamic graph construction and global state.

An agent receives a task and works through it iteratively.  At each iteration
it consults the current state (including everything accumulated so far), plans
the next set of actions, builds a fresh inner tapestry whose topology depends
on those actions, executes it, and folds the results back into state.

The graph changes shape every iteration and every run:

- The planner uses a seeded RNG so different tasks (and even the same task on
  different runs) choose different action types and counts.
- Action types: ``tool_call`` (local function), ``mcp_call`` (simulated remote
  service), ``subagent`` (its own inner-inner tapestry with sub-steps).
- An outer SubTapestry (AgentLoop) owns the iteration loop and the state.
- An inner SubTapestry (ActionDispatcher) builds a dynamic graph per iteration —
  one knot per planned action, running concurrently.

Because history is forwarded, the pirn explorer shows:
- The outer run with a single AgentLoop node
- Drill into AgentLoop → one DispatchIteration node per iteration
- Drill into any DispatchIteration → the actual action knots that ran

Running the six tasks at the bottom produces six structurally different runs.
Re-running produces different paths because the RNG is seeded from a counter
that advances each call.

Run with:
    uv run python examples/llm_agent/agent_loop.py
"""

from __future__ import annotations

import asyncio
import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

MAX_ITERATIONS = 5

# ----------------------------------------------------------------- state models


@dataclass
class StepResult:
    iteration: int
    action_type: str  # "tool_call" | "mcp_call" | "subagent"
    name: str
    output: str


@dataclass
class AgentState:
    task: str
    run_seed: int  # advances per re-run of the same task
    iteration: int = 0
    scratchpad: list[StepResult] = field(default_factory=list)
    done: bool = False
    final_answer: str | None = None


@dataclass
class PlannedAction:
    action_type: str  # "tool_call" | "mcp_call" | "subagent"
    name: str  # e.g. "get_weather", "web_search", "summarise"
    args: dict


# ----------------------------------------------------------------- fake back-ends


def _rng(state: AgentState, extra: str = "") -> random.Random:
    """Deterministic RNG seeded from task + run_seed + iteration + extra."""
    key = f"{state.task}|{state.run_seed}|{state.iteration}|{extra}"
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
            return f"{expr} = {eval(expr, {'__builtins__': {}})}"  # noqa: S307
        except Exception:
            return f"could not evaluate: {expr}"
    if name == "read_file":
        return f"[contents of {args.get('path', '?')}]: lorem ipsum policy text paragraph {rng.randint(1, 9)}"
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
        return (
            f"[page content from {args.get('url', '?')}]: retrieved {rng.randint(200, 800)} words"
        )
    return f"[mcp:{name}] ok"


def _fake_subagent(name: str, args: dict, context: str, rng: random.Random) -> str:
    if name == "summarise":
        words = rng.randint(40, 120)
        return (
            f"Summary ({words} words): {context[:80]}… Key points: {rng.randint(2, 5)} identified."
        )
    if name == "draft_email":
        tone = rng.choice(["professional", "empathetic", "concise"])
        return f"[{tone} email draft] Dear customer, regarding your request: {context[:60]}…"
    if name == "analyse":
        n = rng.randint(2, 6)
        return f"Analysis complete. {n} factors identified from: {context[:60]}…"
    return f"[subagent:{name}] processed: {context[:50]}"


# ----------------------------------------------------------------- planner


def plan_next_actions(state: AgentState) -> list[PlannedAction]:
    """
    Decide what to do next based on task and scratchpad.

    Uses an RNG seeded from task + run_seed + iteration so:
    - The same task produces different plans across re-runs (run_seed increments).
    - Within a run, the plan evolves as the scratchpad grows.
    - Earlier iterations tend to gather data; later ones tend to synthesise.
    """
    rng = _rng(state, extra="plan")
    task = state.task.lower()
    it = state.iteration
    scraped_types = {s.action_type for s in state.scratchpad}

    # If we already have data from prior iterations, move to synthesis.
    if state.scratchpad and it >= 2:
        # Probabilistically decide we're done or need one more synthesis step.
        if rng.random() < 0.55 or it >= MAX_ITERATIONS - 1:
            # Build a final synthesis action over everything accumulated.
            context = " | ".join(s.output for s in state.scratchpad[-3:])
            return [PlannedAction("subagent", "summarise", {"context": context})]

    # First or second iteration: gather data.
    actions: list[PlannedAction] = []

    # Choose action mix based on task keywords + RNG.
    if "weather" in task:
        locs = ["London", "Tokyo", "New York", "Paris", "Berlin"]
        n_locs = rng.randint(1, min(3, 1 + it))  # more locations in later iters
        chosen = rng.sample(locs, n_locs)
        actions += [PlannedAction("tool_call", "get_weather", {"location": l}) for l in chosen]

    if any(w in task for w in ["calculat", "percent", "interest", "cost"]):
        expr = rng.choice(["150 * 1.2", "5000 * 0.035 * 10", "280 * 0.15", "99 * 12"])
        actions.append(PlannedAction("tool_call", "calculate", {"expression": expr}))

    if any(w in task for w in ["research", "find", "look up", "search"]):
        query = task[:60]
        # Sometimes use web_search (MCP), sometimes kb_search (MCP).
        mcp_name = rng.choice(["web_search", "kb_search"])
        actions.append(PlannedAction("mcp_call", mcp_name, {"query": query}))

    if any(w in task for w in ["policy", "refund", "cancel", "plan"]):
        actions.append(PlannedAction("mcp_call", "kb_search", {"query": task[:50]}))

    if any(w in task for w in ["write", "draft", "email", "report", "summarise", "summary"]):
        context = " | ".join(s.output for s in state.scratchpad) or task
        sub_name = rng.choice(["summarise", "draft_email", "analyse"])
        actions.append(PlannedAction("subagent", sub_name, {"context": context[:200]}))

    if any(w in task for w in ["url", "page", "fetch", "scrape"]):
        actions.append(PlannedAction("mcp_call", "fetch_url", {"url": "https://example.com"}))

    # Ensure there's always at least one action.
    if not actions:
        fallback = rng.choice(
            [
                PlannedAction("mcp_call", "web_search", {"query": task[:60]}),
                PlannedAction("tool_call", "get_weather", {"location": "London"}),
                PlannedAction("subagent", "analyse", {"context": task}),
            ]
        )
        actions.append(fallback)

    # Optionally add an extra parallel action for variety.
    if rng.random() < 0.35 and len(actions) < 4 and "subagent" not in scraped_types:
        extras = [
            PlannedAction("mcp_call", "web_search", {"query": f"{task[:30]} latest"}),
            PlannedAction("tool_call", "calculate", {"expression": "100 * 1.035 ** 5"}),
        ]
        actions.append(rng.choice(extras))

    return actions


# ----------------------------------------------------------------- action knots


@knot
async def run_tool_call(action: PlannedAction, state: AgentState, **_) -> StepResult:
    """Execute a local tool function."""
    rng = _rng(state, extra=action.name)
    output = _fake_tool(action.name, action.args, rng)
    return StepResult(
        iteration=state.iteration,
        action_type="tool_call",
        name=action.name,
        output=output,
    )


@knot
async def run_mcp_call(action: PlannedAction, state: AgentState, **_) -> StepResult:
    """Execute a remote MCP service call (simulated)."""
    await asyncio.sleep(0)  # yield — represents async I/O
    rng = _rng(state, extra=action.name)
    output = _fake_mcp(action.name, action.args, rng)
    return StepResult(
        iteration=state.iteration,
        action_type="mcp_call",
        name=action.name,
        output=output,
    )


class SubAgentRunner(SubTapestry):
    """Run a sub-agent as its own inner tapestry.

    The sub-agent builds a two-step inner pipeline:
        prepare_context → execute_subagent
    so it shows up as a drill-down target in the explorer.
    """

    async def process(self, action: PlannedAction, state: AgentState, **_) -> StepResult:  # type: ignore[override]
        rng = _rng(state, extra=action.name)
        context = action.args.get("context", state.task)

        @knot
        async def prepare_context(raw: str, **__) -> str:
            return raw[:300].strip()

        @knot
        async def execute_subagent(ctx: str, **__) -> str:
            return _fake_subagent(action.name, action.args, ctx, rng)

        with Tapestry() as inner:
            raw_p = Parameter(
                "raw",
                str,
                default=context,
                _config=KnotConfig(id="context_input"),
            )
            ctx_knot = prepare_context(raw=raw_p, _config=KnotConfig(id="prepare"))
            execute_subagent(ctx=ctx_knot, _config=KnotConfig(id="subagent_output"))

        result = await self._run_inner(inner)
        output = result.outputs["subagent_output"]
        return StepResult(
            iteration=state.iteration,
            action_type="subagent",
            name=action.name,
            output=output,
        )


# ----------------------------------------------------------------- dispatcher


class ActionDispatcher(SubTapestry):
    """Per-iteration dynamic graph.

    Receives the list of planned actions and builds one knot per action —
    the knot type (ToolCallKnot / MCPCallKnot / SubAgentRunner) depends on
    action_type.  All action knots run concurrently via asyncio.gather
    inside the inner tapestry engine.

    The inner graph is different for every iteration and every run.
    """

    async def process(  # type: ignore[override]
        self,
        actions: list[PlannedAction],
        state: AgentState,
        **_,
    ) -> list[StepResult]:
        with Tapestry() as inner:
            result_knots: dict[str, object] = {}

            for i, action in enumerate(actions):
                node_id = f"{action.action_type}_{action.name}_{i}"
                action_p = Parameter(
                    f"action_{i}",
                    PlannedAction,
                    default=action,
                    _config=KnotConfig(id=f"action_input_{i}"),
                )
                state_p = Parameter(
                    f"state_{i}",
                    AgentState,
                    default=state,
                    _config=KnotConfig(id=f"state_input_{i}"),
                )

                if action.action_type == "tool_call":
                    k = run_tool_call(
                        action=action_p,
                        state=state_p,
                        _config=KnotConfig(id=node_id, validate_io=False),
                    )
                elif action.action_type == "mcp_call":
                    k = run_mcp_call(
                        action=action_p,
                        state=state_p,
                        _config=KnotConfig(id=node_id, validate_io=False),
                    )
                else:  # subagent
                    k = SubAgentRunner(
                        action=action_p,
                        state=state_p,
                        _config=KnotConfig(id=node_id, validate_io=False),
                    )
                result_knots[node_id] = k

            # Aggregate all results into a list.
            Aggregator(
                combine=lambda **kw: list(kw.values()),
                _config=KnotConfig(id="collected", validate_io=False),
                **result_knots,
            )

        dispatch_result = await self._run_inner(inner)
        return dispatch_result.outputs["collected"]


# ----------------------------------------------------------------- agent loop


class AgentLoop(SubTapestry):
    """Iterative agentic loop with global state.

    Each iteration:
      1. Plans the next actions by consulting state.task + state.scratchpad.
      2. Builds and runs a fresh ActionDispatcher (inner tapestry).
      3. Folds new StepResults into state.scratchpad.
      4. Checks whether we're done.

    The same task re-run with an incremented run_seed produces different plans
    because the planner's RNG is seeded from (task, run_seed, iteration).
    """

    async def process(self, state: AgentState, **_) -> AgentState:  # type: ignore[override]
        for _ in range(MAX_ITERATIONS):
            state.iteration += 1

            # Plan next actions — result depends on state contents + RNG.
            actions = plan_next_actions(state)

            # Build a named dispatcher for this iteration.
            dispatcher_id = f"iteration_{state.iteration}"
            with Tapestry() as iter_tapestry:
                actions_p = Parameter(
                    "actions",
                    list,
                    default=actions,
                    _config=KnotConfig(id="planned_actions"),
                )
                state_p = Parameter(
                    "state",
                    AgentState,
                    default=state,
                    _config=KnotConfig(id="current_state"),
                )
                ActionDispatcher(
                    actions=actions_p,
                    state=state_p,
                    _config=KnotConfig(id=dispatcher_id, validate_io=False),
                )

            iter_result = await self._run_inner(iter_tapestry)
            new_results: list[StepResult] = iter_result.outputs[dispatcher_id]
            state.scratchpad.extend(new_results)

            # Check termination: if the last action was a synthesis subagent, we're done.
            if new_results and new_results[-1].action_type == "subagent":
                last = new_results[-1]
                state.done = True
                state.final_answer = last.output
                break

            # Also stop if we've gathered enough data and the RNG says so.
            rng = _rng(state, extra="termination")
            if len(state.scratchpad) >= 3 and rng.random() < 0.5:
                final_ctx = " | ".join(s.output for s in state.scratchpad[-3:])
                state.done = True
                state.final_answer = f"Task complete after {state.iteration} iterations. Key findings: {final_ctx[:150]}"
                break

        if not state.done:
            state.done = True
            state.final_answer = (
                f"Max iterations reached. Partial result from {len(state.scratchpad)} steps."
            )

        return state


# ----------------------------------------------------------------- outer tapestry


def build_tapestry(history=None) -> Tapestry:
    with Tapestry(history=history) as t:
        state = Parameter("state", AgentState, _config=KnotConfig(id="initial_state"))
        AgentLoop(
            state=state,
            _config=KnotConfig(id="agent_loop", validate_io=False),
        )
    return t


# ----------------------------------------------------------------- tasks


# run_seed increments so re-running the same task produces a different graph.
_RUN_COUNTER: dict[str, int] = {}


def _make_state(task: str) -> AgentState:
    _RUN_COUNTER[task] = _RUN_COUNTER.get(task, 0) + 1
    return AgentState(task=task, run_seed=_RUN_COUNTER[task])


TASKS = [
    "What's the weather forecast for my trip to London and Tokyo?",
    "Calculate the compound interest on £5000 at 3.5% for 10 years",
    "Research the latest developments in quantum computing and summarise for me",
    "Find our cancellation policy and draft a customer email explaining it",
    "I need a cost analysis for our Pro plan renewals this quarter",
    "What's the weather in New York and write a brief travel advisory",
]


# ----------------------------------------------------------------- main


async def main() -> None:
    history = SQLiteHistory(path=str(Path(__file__).parent.parent / "pirn.db"))
    t = build_tapestry(history=history)

    _TYPE_ICON = {"tool_call": "⚙", "mcp_call": "🌐", "subagent": "🤖"}

    print("\n── Agentic loop ──\n")

    for task in TASKS:
        state = _make_state(task)
        result = await t.run(RunRequest(parameters={"state": state}))

        if not result.succeeded:
            exc = result.exceptions[0] if result.exceptions else None
            print(f"✗  {task[:55]}")
            print(f"   FAILED: {exc.knot_id if exc else '?'}: {exc.message[:60] if exc else ''}\n")
            continue

        final: AgentState = result.outputs["agent_loop"]
        steps_summary = "  ".join(
            f"{_TYPE_ICON.get(s.action_type, '·')}{s.name}" for s in final.scratchpad
        )
        print(f"✓  {task[:60]}")
        print(f"   {final.iteration} iter · {len(final.scratchpad)} steps · {steps_summary}")
        if final.final_answer:
            print(f"   → {final.final_answer[:100]}")
        print()

    history.close()


if __name__ == "__main__":
    asyncio.run(main())
