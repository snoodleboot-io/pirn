`pirn_agents.specializations` provides 15 pre-built agent pattern families built on top of the agent tier knots — it does not provide LLM clients, vector stores, or tool implementations; those are user-supplied through the agent tier interfaces.

---

## Mental model

Each specialization family is a set of pre-wired knots implementing a well-known agentic pattern. Wire a family into a tapestry by importing its pipeline or individual knots and connecting them to your LLM caller, memory store, and tool set. Families are composable — a RAG pipeline feeds into a guardrails pipeline, for example.

When choosing a family, the key questions are:
1. **Does the agent reason in steps or all at once?** → ReAct, Chain-of-Thought, Reflection
2. **Does it need external knowledge?** → RAG
3. **Does it involve multiple agents?** → Multi-Agent
4. **Does it process documents?** → Document Processing
5. **Does it need structured output?** → Structured Output
6. **Does it need memory across turns?** → Memory Patterns
7. **Is it a pre-built end-to-end agent?** → Specialized Agents

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
│   ├── react_loop.py                ReactLoop                — Thought → Action → Observation loop; terminates on stop signal
│   ├── react_step_executor.py       ReactStepExecutor        — dispatches a single tool call
│   ├── react_step_accumulator.py    ReactStepAccumulator     — builds up trajectory history
│   ├── react_response_extractor.py  ReactResponseExtractor   — extracts Thought/Action/Observation from LLM output
│   ├── react_termination_check.py   ReactTerminationCheck    — decides when to stop the loop
│   └── messages_passthrough.py      MessagesPassthrough      — forwards accumulated messages unchanged
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
from pirn_agents.specializations.react.react_loop import ReactLoop
from pirn import Tapestry, Parameter, KnotConfig, RunRequest

with Tapestry() as t:
    request = Parameter("request", str)
    answer  = ReactLoop(
        request=request,
        tools=[search_tool, calculator_tool],
        llm=my_llm_caller,
        max_steps=10,
        _config=KnotConfig(id="react"),
    )
    OutputSink(answer=answer, _config=KnotConfig(id="out"))

result = await t.run(RunRequest(parameters={"request": "What is the population of Paris?"}))
```

---

## Anti-patterns

**Nesting two ReactLoops** — ReAct is already a loop. Nesting two creates unpredictable recursion depth. Use `multi_agent/OrchestratorAgent` for multi-agent delegation.

**Using `ChainOfThought` and `TreeOfThought` on the same request in sequence** — these are alternative reasoning strategies, not complementary stages. Pick one per decision point.

---

## Constraints and gotchas

- **All specialization knots depend on the agent tier.** The `llm=` argument must be a `LlmCaller` from `pirn_agents.knots`; tool arguments must implement the `Tool` interface.
- **`TreeOfThought` samples N branches in parallel.** Default `branches=3`. Increase LLM rate-limit budget accordingly.
- **`ReactLoop` does not have a built-in timeout.** Set `max_steps` to bound execution. Unbounded loops will run until the LLM stops emitting actions or the process is killed.

---

## Quick reference

| Pattern | Entry point |
|---------|------------|
| Chain-of-thought | `ChainOfThought(request=..., llm=...)` |
| Tree-of-thought | `TreeOfThought(request=..., llm=..., branches=N)` |
| Self-consistency | `SelfConsistencyEnsemble(request=..., llm=..., samples=K)` |
| ReAct loop | `ReactLoop(request=..., tools=[...], llm=..., max_steps=N)` |
| Self-critique/revise | `SelfCritiqueRevise(draft=..., llm=..., max_iters=N)` |
| Route by intent | `IntentRouter(request=..., llm=..., routes={...})` |
| Parallel tool calls | `ParallelToolCaller(request=..., tools=[...])` |
| Multi-turn context | `MultiTurnContextAssembler(history=..., new_message=...)` |

---

*See also: [agents AGENTIC_USE.md](../AGENTIC_USE.md)*
