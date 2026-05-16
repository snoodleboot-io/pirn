# Agentic Loops with LoopSubTapestry

`LoopSubTapestry` is how you build iterative, feedback-driven computation in pirn — the kind of pipeline where the number of steps is not known ahead of time.  Think: an LLM agent refining its answer across multiple tool calls, a training loop that halts on convergence, or a conversational flow that responds to user turns until the session ends.

Every iteration is a real, traceable knot in run history.  This is the defining difference between `LoopSubTapestry` and a bare Python `while` loop hidden inside a `Knot.process()` — pirn's explorer can drill into each step, replay any iteration, and attribute latency to individual turns.

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

The `updated_state` you return alongside the tapestry is passed to `fold` once the iteration completes — it represents your prediction or bookmark, not the iteration's output.

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

## Zero-Iteration Loops

If `step(initial_state)` returns `None` immediately, the loop completes with the initial state as output and a single `__loop_terminal__` knot in history.  No exception is raised.

## Relationship to SubTapestry

`LoopSubTapestry` is a `SubTapestry` variant with two extensions:

1. The inner tapestry runs in **extensible mode** — knots may be registered mid-run as each iteration completes.
2. The output is always read from the `__loop_terminal__` knot, regardless of what `process()` returns, because the true terminal is registered mid-run by the last iteration rather than by `process()` itself.

Everything else — input wiring, history propagation, `Err`/`Ok` wrapping, `validate_io` — is identical to `SubTapestry`.  See [sub-tapestry.md](sub-tapestry.md) for the base contract.
