# PAE-F8 — Agentic Design Patterns: Taxonomy & Investigation (PIR-21 / S1)

**Status:** implementation set locked (S2–S8).
**Scope:** the standard agentic patterns not yet in `PATTERNS.md`, each realised as a
provider-neutral `SubTapestry` (or a small set of `Knot`s) that reuses the existing
building blocks. Provider-neutral throughout: no LLM/tool/memory vendor is favoured; all
concrete providers are user-supplied through the agent-tier interfaces
(`LLMProvider`, `Tool`, `MemoryStore`, `EmbeddingProvider`).

---

## 1. Method

Each candidate pattern is (a) described from its primary literature, (b) mapped to the
**concrete knots** that implement it, and (c) classified **net-new** (introduces genuinely
new control flow) vs. **compositional** (a wiring of knots that already exist). The
implementation set was chosen to maximise capability/perf coverage while reusing F1
(tool-call protocol + parallel executor), F3 (LLM providers), F4 (memory/vector),
F7 (agents-as-tools), and F10 (run budgets).

## 2. Reused building blocks

| Block | Module | Used by |
|-------|--------|---------|
| Parallel bounded-concurrency tool executor (F1) | `parallel_tool_executor.ParallelToolExecutor` | ReWOO, Orchestrator-Workers |
| Toolset / ToolCall / ToolResult (F1) | `toolset`, `types/tool_call`, `types/tool_result` | ReWOO, Router+Fallback, Orchestrator-Workers |
| LLM provider interface (F3) | `pirn.core.providers.llm_provider.LLMProvider` | all |
| Memory store interface (F4) | `memory_store.MemoryStore` | Reflexion |
| Agents-as-tools (F7) | `agent_tool.AgentTool` | Orchestrator-Workers |
| Run budget + meter (F10) | `performance.run_budget.RunBudget`, `run_budget_meter.RunBudgetMeter` | LATS |
| Existing binary reflection gate | `control.reflection_check.ReflectionCheck` | Evaluator-Optimizer (generalised) |
| Existing planner / ReAct loop | `plan_and_execute.task_planner.TaskPlanner`, `react.react_loop.ReActLoop` | Plan-ReAct |

## 3. Pattern taxonomy

| # | Pattern | Story | Classification | Concrete knots (new) | Primary reference |
|---|---------|-------|----------------|----------------------|-------------------|
| 1 | **ReWOO** — plan all tool calls up front, execute in parallel, single synthesis | S2 | **net-new** control flow (decoupled planner/worker/solver), reuses F1 executor | `ReWooPlanner`, `ReWooSynthesizer`, `ReWooPipeline`, `ReWooResult` | Xu et al. 2023, *ReWOO* (arXiv:2305.18323) |
| 2 | **Reflexion** — actor → evaluator → verbal self-reflection persisted to memory across attempts | S3 | **net-new** (memory-backed retry loop) | `ReflexionActor`, `ReflexionEvaluator`, `ReflexionReflector`, `ReflexionPipeline`, `ReflexionAttempt`, `ReflexionResult` | Shinn et al. 2023 (arXiv:2303.11366) |
| 3 | **Evaluator-Optimizer** — generator + LLM-as-judge with a scored accept gate | S4 | **compositional++** (generalises `ReflectionCheck` from boolean to scored) | `CandidateGenerator`, `LlmJudge`, `JudgeVerdict`, `EvaluatorOptimizerPipeline`, `EvaluatorOptimizerResult` | Madaan et al. 2023 *Self-Refine* (arXiv:2303.17651); Anthropic "Building effective agents" (2024) |
| 4 | **Router + typed Fallback chain** — confidence dispatch + ordered fallback on failure/low-confidence | S5 | **compositional** (extends `routing/`, reuses `ConfidenceRouter`) | `RouteCandidate`, `CandidateRouter`, `FallbackChain`, `FallbackResult`, `RouterFallbackPipeline` | Anthropic "Building effective agents" — routing (2024) |
| 5 | **Orchestrator-Workers** — dynamic worker spawn over a task list, bounded concurrency, via F7 | S6 | **net-new** (dynamic fan-out) reusing F7 `AgentTool` + F1 semaphore | `OrchestratorWorkers`, `WorkerTaskResult`, `OrchestratorWorkersResult` | Anthropic "Building effective agents" — orchestrator-workers (2024) |
| 6 | **LATS / tree-search act** — budgeted MCTS-style search over action trajectories scored by a value model | S7 | **net-new** (search) reusing F10 budget | `TrajectoryValueModel`, `LatsActionProposer`, `LatsNode`, `LatsResult`, `LatsSearch` | Zhou et al. 2024 *Language Agent Tree Search* (arXiv:2310.04406) |
| 7 | **Self-Ask** — decompose into sub-questions, answer each, compose | S8 | **compositional** | `SelfAskPipeline`, `SelfAskResult` | Press et al. 2022 (arXiv:2210.03350) |
| 8 | **Plan-ReAct** — plan first (`TaskPlanner`), then ReAct per step (`ReActLoop`) | S8 | **compositional** (pure reuse) | `PlanReActPipeline`, `PlanReActResult` | Yao et al. 2023 ReAct + Plan-and-Solve |
| 9 | **Prompt-chaining** — fixed sequence of LLM calls, each output feeds the next | S8 | **compositional** | `PromptChainPipeline`, `PromptChainResult` | Anthropic "Building effective agents" — prompt chaining (2024) |

## 4. Net-new vs. compositional summary

- **Net-new control flow:** ReWOO (S2), Reflexion (S3), Orchestrator-Workers (S6), LATS (S7).
- **Compositional (wire existing knots / generalise an existing gate):** Evaluator-Optimizer
  (S4, generalises `ReflectionCheck`), Router+Fallback (S5, extends `routing/`),
  Self-Ask / Plan-ReAct / Prompt-chaining (S8).

## 5. Cross-cutting conventions

- Every top-level pattern is a `SubTapestry` with `__init__` → `process`, `isinstance`
  validation at `process` time, and a **typed result** dataclass (`PirnOpaqueValue`).
- Iteration is bounded by `max_iterations` (and, for LATS, an explicit `RunBudget`
  node/time budget); no pattern runs unbounded.
- Each pattern ships **mirrored tests** with stub doubles (`StubLLMProvider`, `StubTool`,
  `StubMemoryStore`, stub value model) and a `@pytest.mark.benchmark` micro-bench.
- Documentation: a `PATTERNS.md` section + an `AGENTIC_USE.md` entry with wiring code.

## 6. Performance rationale

- **ReWOO** collapses N sequential ReAct round-trips into **2** LLM calls (plan + synthesise)
  and runs the N tool calls concurrently through the F1 executor.
- **Router+Fallback** avoids wasted retries by dispatching to the best candidate first and
  only falling back on real failure/low-confidence, rather than blindly retrying one path.
- **Orchestrator-Workers** parallelises independent sub-tasks under a concurrency bound.
- **LATS** is strictly budget-bounded (node count + wall-clock) so search never runs away.
