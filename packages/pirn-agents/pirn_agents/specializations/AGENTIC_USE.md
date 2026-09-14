`pirn_agents.specializations` provides 67 pre-built agentic patterns (`AgentPatternRegistry.pattern_names()` is the source of truth for the count — see `pirn_agents/PATTERNS.md`), each an ordinary `SubTapestry` built on the agent-domain knots described in `../AGENTIC_USE.md`; a pattern whose reasoning genuinely repeats until a condition is met (ReAct's inner step, self-ask, reflexion, the RAG retry loops, the structured-output retry loops, and others) wires that repetition as `LoopSubTapestry` (via the shared `AgentLoopPipeline[S]` base, ADR agents-speaks-core WS5b) rather than a Python `while`, so every iteration is its own traceable knot in run history. This package does not provide LLM clients, vector stores, or tool implementations — those are user-supplied through the `LLMProvider`, `MemoryStore`, and `Tool` interfaces.

---

## Mental model

Each pattern is a `SubTapestry` — a pre-wired knot graph implementing a well-known agentic construct — wired the same way any other knot is: pass its constructor an `LLMProvider`, a `MemoryStore`, and/or a sequence of `Tool`s, place it in a `Tapestry`, and run it. Its outcome is the engine's own `Ok | Err | Skipped`, and its typed result travels as this domain's `Payload` types (`AgentResponse = Payload[GenerationFrame, str]`, `ConversationPayload = Payload[ConversationFrame, tuple[AgentMessage, ...]]`) or a pattern-specific result value. Patterns are composable — a RAG pipeline feeds into a guardrails pipeline, for example, because both are just knots.

When choosing a pattern, the key questions are:
1. **Does the agent reason in steps or all at once?** → ReAct, Chain-of-Thought, Reflection
2. **Does it need external knowledge?** → RAG
3. **Does it involve multiple agents?** → Multi-Agent
4. **Does it process documents?** → Document Processing
5. **Does it need structured output?** → Structured Output
6. **Does it need memory across turns?** → Memory Patterns
7. **Is it a pre-built end-to-end agent?** → Specialized Agents

---

## Two ways to wire a pattern, and they meet

This document is the **knot-first** way: import a pipeline class, pass its
constructor your `LLMProvider`, `MemoryStore` and tools, and place it in a
`Tapestry`. That is the substrate, and nothing below is builder-only.

`pirn_agents/builder/BUILDER.md` documents the declarative surface over the
same thing: `AgentBuilder` (fluent Python) and `AgentSpec` (the same
configuration as data — a projection of core's `PipelineSpec`, via
`.to_pipeline_spec()` / `AgentSpec.from_pipeline_spec()`), with `AgentPresets`
as named entries and `AgentPatternRegistry` as the one pattern table — every
name in it is also registered under core's own `sweet_tea` registry, so a core
YAML pipeline document can name a pattern (`type: react`) directly and
`tapestry-check` validates it. All 67 patterns in this tree are reachable by
name through it.

The two are not layers you must choose between:

- `Agent.builder()...build()` returns an ordinary `SubTapestry` — wire it as a
  parent of your own hand-built knots, or vice versa, in one `Tapestry`.
- Everything the facade will generate is readable first: `.pattern_class` is the
  class you would have imported, `.knot_id` the id it will take, `.to_pipeline_spec()`
  the whole configuration as a core `PipelineSpec`.
- `AgentPatternRegistry.describe(name)` reports a pattern's constructor contract
  — required components and optional knobs — whether or not you use the builder
  to satisfy it.

Reach for the declarative surface when a configuration is named, repeated, or
comes from a config file. Reach for raw knots when the graph is one-off or when
you are composing a pattern into something larger. There is no boundary
between them.

---

## Sub-package index

| Sub-package | Pattern | Guide |
|-------------|---------|-------|
| `rag/` | Retrieval-augmented generation (naive, corrective, self, multi-hop, graph, HyDE, adaptive) | [AGENTIC_USE.md](rag/AGENTIC_USE.md) |
| `multi_agent/` | Orchestrator-worker, parallel fan-out, consensus, debate framework | [AGENTIC_USE.md](multi_agent/AGENTIC_USE.md) |
| `guardrails/` | Input/output safety gates, hallucination detection, PII redaction, fact-checking | [AGENTIC_USE.md](guardrails/AGENTIC_USE.md) |
| `structured_output/` | JSON/YAML/Enum/Pydantic extraction pipelines with retry-on-parse-failure | [AGENTIC_USE.md](structured_output/AGENTIC_USE.md) |
| `memory_patterns/` | Working, episodic, semantic, procedural memory pipelines | [AGENTIC_USE.md](memory_patterns/AGENTIC_USE.md) |
| `document_processing/` | Ingestion, QA, summarization, translation over documents | [AGENTIC_USE.md](document_processing/AGENTIC_USE.md) |
| `specialized_agents/` | Research, browser, code, SQL, data analyst end-to-end agents | [AGENTIC_USE.md](specialized_agents/AGENTIC_USE.md) |
| `chain_of_thought/` | CoT, Tree-of-Thought, Step-Back, Self-Consistency | — (single knot each; see source map below) |
| `react/` | ReAct loop: observe → think → act → repeat | — (see source map below) |
| `reflection/` | Self-critique → revise loop with constitutional filter | — (see source map below) |
| `routing/` | Intent, confidence, and capability-based routing | — (see source map below) |
| `conversation/` | Multi-turn context assembly and memory pruning | — (see source map below) |
| `tool_use/` | Tool selection, parallel calling, chain, validation, result formatting | — (see source map below) |
| `human_in_the_loop/` | ApprovalCheck, ClarificationRequester, EscalationRouter | — (covered in agents AGENTIC_USE.md) |
| `plan_and_execute/` | TaskPlanner, PlanExecutor, PlanRevisor | — (covered in agents AGENTIC_USE.md) |

---

## Source map (simple sub-packages)

```
pirn_agents/specializations/
│
│  ── Chain-of-thought ──
├── chain_of_thought/
│   ├── chain_of_thought.py          ChainOfThought           — prepend CoT reasoning prefix; extract final answer
│   ├── tree_of_thought.py           TreeOfThought            — branch N reasoning paths; vote on best
│   ├── step_back_prompting.py       StepBackPrompting        — abstract before solving (step-back technique)
│   └── self_consistency_ensemble.py SelfConsistencyEnsemble  — sample K completions; majority-vote answer
│
│  ── ReAct ──
├── react/
│   ├── react_loop.py                ReActLoop                — Thought → Action → Observation loop; terminates on stop signal
│   ├── react_step_executor.py       ReActStepExecutor        — dispatches a single tool call
│   ├── react_step_accumulator.py    ReActStepAccumulator     — builds up trajectory history
│   ├── react_response_extractor.py  ReActResponseExtractor   — extracts Thought/Action/Observation from LLM output
│   └── react_termination_check.py   ReActTerminationCheck    — decides when to stop the loop
│
│  ── Reflection ──
├── reflection/
│   ├── self_critique_revise.py      SelfCritiqueRevise       — critique → revise cycle; N max iterations
│   ├── constitutional_filter.py     ConstitutionalFilter     — block outputs that violate a constitution
│   ├── outcome_simulator.py         OutcomeSimulator         — simulate outcome before committing action
│   └── simulation_result.py        SimulationResult         — value type: simulator output
│
│  ── Routing ──
├── routing/
│   ├── intent_router.py             IntentRouter             — classify intent; branch to handler knot
│   ├── confidence_router.py         ConfidenceRouter         — branch on confidence score threshold
│   └── capability_router.py         CapabilityRouter         — route to agent with declared matching capability
│
│  ── Conversation ──
├── conversation/
│   ├── multi_turn_context_assembler.py  MultiTurnContextAssembler  — build message list from turn history
│   └── conversation_memory_pruner.py   ConversationMemoryPruner   — trim history to fit context window
│
│  ── Tool use ──
└── tool_use/
    ├── tool_selector.py             ToolSelector             — pick tool(s) from registry given request
    ├── parallel_tool_caller.py      ParallelToolCaller       — call multiple tools concurrently
    ├── tool_chain.py                ToolChain                — call tools sequentially, passing results forward
    ├── tool_call_validator.py       ToolCallValidator        — validate tool args before calling
    └── tool_result_formatter.py    ToolResultFormatter      — format tool outputs for LLM consumption
```

---

## Canonical pattern — ReAct with tools

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.messaging.agent_message import AgentMessage

with Tapestry() as t:
    ReActLoop(
        messages=(AgentMessage(role="user", content="What is the population of Paris?"),),
        tools=[search_tool, calculator_tool],
        llm=my_llm_provider,
        max_iterations=10,
        _config=KnotConfig(id="react"),
    )

result = await t.run(RunRequest())
answer = result.outputs["react"]   # an AgentResponse = Payload[GenerationFrame, str]
print(answer.data)
```

---

## Anti-patterns

**Nesting two `ReActLoop`s** — ReAct is already a loop. Nesting two creates unpredictable recursion depth (core's `RunNesting` guard will refuse it past a configured `max_nesting_depth`). Use `multi_agent/OrchestratorAgent` for multi-agent delegation.

**Using `ChainOfThought` and `TreeOfThought` on the same request in sequence** — these are alternative reasoning strategies, not complementary stages. Pick one per decision point.

---

## Constraints and gotchas

- **Every pattern depends on the agent-domain interfaces.** The `llm=` argument must be an `LLMProvider` (`pirn_agents.llm.llm_provider.LLMProvider`); tool arguments must be a `Tool` class, a `ToolFactory`, or a `@tool`-decorated callable.
- **`TreeOfThought` samples `k_candidates` branches to `depth`, `beam_width` wide.** Defaults `k_candidates=3`, `beam_width=2`, `depth=3`. Increase LLM rate-limit budget accordingly.
- **`ReActLoop` is a fixed-length unrolled `SubTapestry`, not an unbounded loop.** `max_iterations` (default `10`) caps the number of step knots the inner tapestry contains; a run that finishes early short-circuits the remaining steps rather than skipping their cost entirely.

---

## Quick reference

| Pattern | Entry point |
|---------|------------|
| Chain-of-thought | `ChainOfThought(prompt=..., llm=...)` |
| Tree-of-thought | `TreeOfThought(prompt=..., llm=..., k_candidates=N, beam_width=W, depth=D)` |
| Self-consistency | `SelfConsistencyEnsemble(prompt=..., llm=..., samples=K)` |
| ReAct loop | `ReActLoop(messages=(...,), tools=[...], llm=..., max_iterations=N)` |
| Self-critique/revise | `SelfCritiqueRevise(prompt=..., llm=...)` |
| Route by intent | `IntentRouter(message=..., llm=..., categories=[...])` |
| Parallel tool calls | `ParallelToolCaller(tool_calls=[...], tools=[...])` |
| Multi-turn context | `MultiTurnContextAssembler(messages=(...,), max_turns=N, max_tokens=T)` |

---

## F8 — Agentic Design Patterns expansion (PIR-21)

Nine additional pattern families (see `PATTERNS_TAXONOMY_F8.md` for the net-new vs.
compositional classification and citations, and `PATTERNS.md` Patterns 19-27 for full
wiring code). All are provider-neutral `SubTapestry`s that reuse F1 (parallel executor),
F4 (memory), F7 (agents-as-tools), and F10 (run budgets).

| Sub-package | Pattern | Entry point | Typed result |
|-------------|---------|-------------|--------------|
| `rewoo/` | ReWOO: plan-all → parallel-exec → synthesise (2 LLM round-trips) | `ReWooPipeline(goal=..., llm=..., tools=[...])` | `ReWooResult` |
| `reflexion/` | Reflexion: actor/evaluator/reflection with F4 memory read-back | `ReflexionPipeline(task=..., llm=..., memory=...)` | `ReflexionResult` |
| `evaluator_optimizer/` | Generator + LLM-judge + scored accept gate (generalises `ReflectionCheck`) | `EvaluatorOptimizerPipeline(task=..., llm=..., threshold=8.0)` | `EvaluatorOptimizerResult` |
| `routing/` (extended) | Confidence router + typed fallback chain | `RouterFallbackPipeline(candidates=[...], confidences={...}, arguments={...})` | `FallbackResult` |
| `multi_agent/` (extended) | Orchestrator-Workers: dynamic fan-out via F7 `AgentTool` | `OrchestratorWorkers(tasks=[...], worker=AgentTool(...), max_concurrency=N)` | `OrchestratorWorkersResult` |
| `lats/` | LATS: budgeted best-first tree search, pluggable value model (F10 budget) | `LatsSearch(task=..., llm=..., value_model=..., budget=RunBudget(...))` | `LatsResult` |
| `self_ask/` | Self-Ask: sub-question decomposition | `SelfAskPipeline(task=..., llm=...)` | `SelfAskResult` |
| `plan_react/` | Plan-ReAct: `TaskPlanner` then `ReActLoop` per step | `PlanReActPipeline(task=..., llm=..., tools=[...])` | `PlanReActResult` |
| `prompt_chaining/` | Prompt-chaining: sequential LLM calls, each output feeds the next | `PromptChainPipeline(task=..., llm=..., steps=[...])` | `PromptChainResult` |

### Constraints and gotchas (F8)

- **Bounded by construction.** ReWOO is a fixed two round-trips; Reflexion / Evaluator-Optimizer
  are capped by `max_iterations`; LATS is capped by a `RunBudget` (node count and/or deadline) and
  refuses an unbounded budget; Orchestrator-Workers is capped by `max_concurrency`.
- **Provider-neutral.** All patterns take an `LLMProvider`, `Tool`, `MemoryStore`, or
  `TrajectoryValueModel` you supply; nothing favours a specific vendor. Stub doubles drive every test.
- **ReWOO parallelism** flows through the F1 `ParallelToolExecutor`; independent tool calls run
  concurrently under `max_concurrency`.
- **Reflexion memory** is any `MemoryStore` — reflections are written under `"<namespace>:<i>"` keys
  and read back on the next attempt.

---

*See also: [agents AGENTIC_USE.md](../AGENTIC_USE.md)*
