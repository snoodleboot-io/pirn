# Agentic Loops with LoopSubTapestry

`LoopSubTapestry` is how you build iterative, feedback-driven computation in pirn — the kind of pipeline where the number of steps is not known ahead of time.  Think: an LLM agent refining its answer across multiple tool calls, a training loop that halts on convergence, or a conversational flow that responds to user turns until the session ends.

Every iteration is a real, traceable knot in run history.  This is the defining difference between `LoopSubTapestry` and a bare Python `while` loop hidden inside a `Knot.process()` — pirn's explorer can drill into each step, replay any iteration, and attribute latency to individual turns.

> **Iteration bound.** Iterations chain through parent edges, and resolving that chain costs stack depth proportional to its length. Past roughly 950 iterations (at CPython's default recursion limit of 1000) a run fails with `RecursionError` recorded against the loop knot — `succeeded=False`, so it fails loudly rather than returning a wrong answer. This is comfortably above bounded agent loops, which run 3–20 iterations, but a genuinely open-ended conversational session should not assume it can run indefinitely. Tracked separately; see PIR-763.

## Core Concepts

### Why Not a Python `while` Loop?

A `while` loop inside `process()` is opaque: it produces one output, one timeline entry, and zero drill-down capability.  `LoopSubTapestry` instead registers each iteration as its own knot in an extensible inner run:

```
outer tapestry
  └─ my_loop (LoopSubTapestry)
       └─ inner tapestry (extensible)
            ├─ step_1 (_IterationChainKnot)
            ├─ step_2 (_IterationChainKnot)  ← registered by step_1 at runtime
            ├─ step_3 (_IterationChainKnot)  ← registered by step_2 at runtime
            └─ __loop_terminal__             ← registered by step_3 at runtime
```

Each `step_N` is a child run of the outer loop run.  Sub-tapestries spawned inside an iteration appear in the same history store and are reachable via the explorer's drill-down navigation.

### State Is Explicit

All information the loop needs to carry between iterations lives in a single `state` value.  The framework threads it through without mutation or shared variables.  There is no hidden channel between iterations.

## The `step` / `fold` Contract

Subclass `LoopSubTapestry[S]` and implement two methods:

```python
def step(self, state: S) -> tuple[Tapestry, S] | None:
    ...

def fold(self, state: S, result: RunResult) -> S:
    ...
```

### `step(state) -> tuple[Tapestry, S] | None`

Called before each iteration.  Given the current state, decide:

- **Continue**: build the iteration's tapestry, return `(tapestry, updated_state)`.
- **Terminate**: return `None`.

The second element of the return tuple is the state `fold` will receive for that iteration. Returning `state` unchanged is still the simplest convention — and is what you want whenever `step` mutates a shared state object in place — but a `step` that computes a *new* state value can return it and `fold` will see it.

> **Changed in PIR-754.** This previously read "the second element is ignored; `fold` always receives the state passed into `step`". That described a defect, not a contract: the framework honoured `step`'s returned state on iteration 1 and discarded it on every later iteration, so the two disagreed with each other. `fold` now receives `step`'s returned state on every iteration, matching `LoopSubTapestry`'s own class docstring. A `step` that returns `state` unchanged — the documented convention, and what every in-tree loop does — is unaffected.

Build the iteration tapestry with a plain `Tapestry()` context manager:

```python
def step(self, state: ConvState) -> tuple[Tapestry, ConvState] | None:
    if state.done or state.turns >= self.max_turns:
        return None
    with Tapestry() as t:
        LLMCallKnot(
            messages=state.messages,
            _config=KnotConfig(id="llm"),
        )
    return t, state
```

### `fold(state, result) -> S`

Called after each iteration completes.  Integrate the iteration's `RunResult` into state and return the new state:

```python
def fold(self, state: ConvState, result: RunResult) -> ConvState:
    reply = result.outputs["llm"]
    return ConvState(
        messages=[*state.messages, {"role": "assistant", "content": reply}],
        done=reply.strip().endswith("[DONE]"),
        turns=state.turns + 1,
    )
```

### Execution Order

```
initial state
  → step(state)         # plan iteration 1 or terminate
  → [run iteration 1]
  → fold(state, result) # integrate result → new_state
  → step(new_state)     # plan iteration 2 or terminate
  → [run iteration 2]
  → fold(...)
  → ...
  → step(...)           # returns None → terminate
  → final state surfaced as this knot's output
```

## Wiring Into a Tapestry

`LoopSubTapestry` is a `Knot`.  Wire it the same way as any other knot.

The `state` input is the initial loop state.  Pass it as a plain Python value (treated as a config constant, invisible in lineage) or as an upstream `Knot` (resolved at run time and visible in lineage):

```python
# Option A — plain initial state (most common for self-contained loops)
with Tapestry() as t:
    MyAgentLoop(
        state=MyState(turns=0, done=False),   # plain value → config constant
        max_turns=10,
        _config=KnotConfig(id="agent"),
    )

result = await t.run(RunRequest())
final_state = result.outputs["agent"]

# Option B — initial state from an upstream knot
with Tapestry() as t:
    context_builder = BuildContext(_config=KnotConfig(id="ctx"))
    MyAgentLoop(
        state=context_builder,                 # Knot → resolved value arrives in process()
        max_turns=10,
        _config=KnotConfig(id="agent"),
    )

result = await t.run(RunRequest())
final_state = result.outputs["agent"]
```

## Full Example: Conversational LLM Agent

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.nodes.loop_sub_tapestry import LoopSubTapestry
from pirn.tapestry import Tapestry

# LLMCallKnot is a placeholder — replace with your actual LLM knot implementation.

@dataclass
class ConvState:
    messages: list[dict[str, str]] = field(default_factory=list)
    turns: int = 0
    done: bool = False


class ConversationalAgent(LoopSubTapestry[ConvState]):

    def __init__(self, *, max_turns: int = 20, **kwargs: Any) -> None:
        self._max_turns = max_turns
        super().__init__(**kwargs)

    def step(self, state: ConvState) -> tuple[Tapestry, ConvState] | None:
        if state.done or state.turns >= self._max_turns:
            return None
        with Tapestry() as t:
            LLMCallKnot(
                messages=state.messages,
                _config=KnotConfig(id="llm"),
            )
        return t, state

    def fold(self, state: ConvState, result: RunResult) -> ConvState:
        reply = result.outputs["llm"]
        return ConvState(
            messages=[*state.messages, {"role": "assistant", "content": reply}],
            turns=state.turns + 1,
            done="[DONE]" in reply,
        )

    def step_id(self, state: ConvState, idx: int) -> str:
        return f"turn_{idx}"
```

Wire it up:

```python
with Tapestry() as t:
    ConversationalAgent(
        state=ConvState(messages=[{"role": "user", "content": "Hello!"}]),
        max_turns=10,
        _config=KnotConfig(id="agent"),
    )

result = await t.run(RunRequest())
final: ConvState = result.outputs["agent"]
```

Explorer drill-down shows `turn_1`, `turn_2`, … as individual child knots, each with its own LLM call sub-run.

## Customising Step IDs

Override `step_id(state, idx)` to produce meaningful names in run history:

```python
def step_id(self, state: ConvState, idx: int) -> str:
    return f"turn_{idx}"
```

Default is `step_{idx}`.  The method is called with the state *before* that step's tapestry runs, so you can embed state-derived labels.

## Observability

Because every iteration is a knot:

- **Run history** shows each iteration's start time, end time, and output.
- **Explorer drill-down** reaches into any iteration's inner tapestry.
- **Parent/child links** connect the loop run to its per-iteration sub-runs.
- **Failures** surface at the iteration level — a failed `step_3` does not erase `step_1` and `step_2` from history.

## Concurrency and Dispatchers

A `Dispatcher` decides **where** a single knot's coroutine runs — not whether sibling knots overlap.  Concurrency between knots is the engine's job, and it already happens by default: for each ready wave the engine wraps every knot in `asyncio.create_task` (`pirn/engine/engine.py`) and awaits the wave together, so the default `LocalDispatcher` runs a whole wave of ready knots concurrently on the event loop.  Swapping in another dispatcher changes only the execution *location* of each knot; it does not add or remove sibling concurrency.

### Speeding up a nested agent loop

To move the whole nested subtree off the event loop and onto a worker thread — useful when a loop mixes CPU-ish orchestration with async I/O — set a `ThreadDispatcher` on the **outer** `Tapestry`:

```python
from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher

with Tapestry(dispatcher=ThreadDispatcher()) as t:
    ...  # your LoopSubTapestry and its inner tapestry
```

This is the **supported** escape: the outer dispatcher carries the entire nested subtree — including agent-as-tool invocations — into the worker thread, with no change required on the agents side.

### Do not set a dispatcher on an *inner* tapestry

Setting a per-**inner**-tapestry dispatcher (for example a `ThreadDispatcher` on a `SubTapestry`/`LoopSubTapestry`'s own inner tapestry) is **not supported and is unsafe** for agent-as-tool workloads.  The agent-as-tool machinery binds an `AgentToolContext` into a `contextvars` context (read by `current_agent_tool_context()` in `pirn_agents/agent/agent_invoker.py`).  An inner dispatcher crosses the thread boundary *after* that bind, and `loop.run_in_executor` — unlike `asyncio.to_thread` — does **not** copy the context into the worker thread.  The inner knot then sees no context, so `agent_invoker.py` falls back to a fresh **root** `AgentToolContext`:

```python
parent = current_agent_tool_context()          # None across the uncopied boundary
base = parent if parent is not None else AgentToolContext(max_depth=self._max_depth)
```

That silently resets `depth` to the root and drops the inherited cycle set and budget meter, defeating `AgentDepthExceededError`, `AgentCycleError`, and `BudgetBreachError`.  The **outer**-dispatcher configuration above is safe precisely because the bind happens *inside* the worker thread, so there is no boundary to cross afterward.

### Blocking work inside a knot

For blocking work *within* a single knot's `process()`, the idiom is `asyncio.to_thread(...)`, which copies the calling `contextvars` context into the thread (again, `run_in_executor` does not).  This keeps the active `AgentToolContext` — and therefore the depth, cycle, and budget guards — intact.

## Zero-Iteration Loops

If `step(initial_state)` returns `None` immediately, the loop completes with the initial state as output and a single `__loop_terminal__` knot in history.  No exception is raised.

## Relationship to SubTapestry

`LoopSubTapestry` is a `SubTapestry` variant with two extensions:

1. The inner tapestry runs in **extensible mode** — knots may be registered mid-run as each iteration completes.
2. The output is always read from the `__loop_terminal__` knot, regardless of what `process()` returns, because the true terminal is registered mid-run by the last iteration rather than by `process()` itself.

Everything else — input wiring, history propagation, `Err`/`Ok` wrapping, `validate_io` — is identical to `SubTapestry`.  See [sub-tapestry.md](sub-tapestry.md) for the base contract.
