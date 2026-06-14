# AGENTIC_USE — pirn.domains.agents

This domain provides knots and interfaces for building LLM-backed pipelines in pirn; it does **not** ship any concrete LLM, vector-store, or tool implementations — those are always user-supplied.

---

## Mental model

Agent behaviour in pirn is expressed as an ordinary knot graph. There is no hidden runtime loop; the agent loop *is* your pipeline. Five tiers of knots cover the full lifecycle: **Input** (parse raw text, classify intent, build context), **Generation** (call an LLM, parse and format the response), **Planning** (produce a plan, route steps to tools, execute and aggregate results), **Memory** (write and retrieve conversation state), and **Control** (gate iteration, enforce safety, detect termination or escalation).

The three things you must supply are a concrete **LLMProvider**, one or more **Tool** implementations, and optionally a **MemoryStore**. Every agent knot depends only on these interfaces; pirn never imports a vendor SDK directly. This keeps the `pirn[agents]` extra lightweight and your application free to choose any backend.

All three interfaces inherit from `PirnOpaqueValue`. pirn serialises them by identity rather than by inspecting their internals, so content-addressing cache stays stable even when providers hold live SDK state or open connections.

---

## Install

```bash
pip install pirn[agents]

# Add your chosen LLM provider SDK separately:
pip install anthropic          # Anthropic
pip install openai             # OpenAI-compatible APIs

# If you need a vector store for memory:
pip install pinecone-client    # or qdrant-client, weaviate-client, etc.
```

---

## Source map

```
pirn/domains/agents/
├── llm_provider.py              LLMProvider           — interface you must implement
├── tool.py                      Tool                  — interface you must implement
├── tool_decorator.py            @tool / FunctionTool  — shorthand for plain functions
├── memory_store.py              MemoryStore           — interface you must implement
├── types/
│   ├── agent_message.py         AgentMessage          — single conversation turn
│   ├── agent_context.py         AgentContext          — full message tuple + metadata
│   ├── agent_response.py        AgentResponse         — one agent turn result
│   ├── plan.py                  Plan                  — ordered tuple of step strings
│   ├── tool_call.py             ToolCall              — LLM-requested tool invocation
│   └── tool_result.py           ToolResult            — outcome of executing a ToolCall
├── input/
│   ├── message_parser.py        MessageParser         — raw input → AgentMessage tuple
│   ├── context_builder.py       ContextBuilder        — messages + system_prompt → AgentContext
│   └── intent_classifier.py     IntentClassifier      — context → intent label string
├── generation/
│   ├── llm_call.py              LLMCall               — AgentContext → raw response mapping
│   ├── streaming_llm_call.py    StreamingLLMCall      — returns AsyncIterator of chunks
│   ├── output_parser.py         OutputParser          — raw response → AgentResponse
│   └── response_formatter.py    ResponseFormatter     — AgentResponse → display string
├── planning/
│   ├── planner.py               Planner               — context → Plan
│   ├── tool_router.py           ToolRouter            — plan step string → ToolCall
│   ├── tool_executor.py         ToolExecutor          — ToolCall → ToolResult
│   └── tool_result_aggregator.py ToolResultAggregator — [ToolResult] → {call_id: result}
├── memory/
│   ├── memory_writer.py         MemoryWriter          — write key/value to MemoryStore
│   ├── memory_retriever.py      MemoryRetriever       — retrieve by key or similarity
│   └── conversation_buffer.py   ConversationBuffer    — sliding window of turns
├── control/
│   ├── safety_check.py          SafetyCheck           — regex deny-list → bool
│   ├── termination_check.py     TerminationCheck      — finish_reason / iteration cap → bool
│   ├── reflection_check.py      ReflectionCheck       — LLM quality gate → bool
│   └── handoff_check.py         HandoffCheck          — escalation pattern → bool
└── specializations/             ← specializations
    ├── react/                   ReActLoop             — SubTapestry: reason+act loop
    ├── rag/                     Naive / Corrective / HyDe / Graph RAG pipelines
    │                            SelfRAG, AdaptiveRAG, MultiHopRAG, Reranker, RAGSynthesizer
    ├── multi_agent/             OrchestratorAgent, ParallelSpecialistFanOut, DebateFramework,
    │                            ConsensusAggregator, RoundRobinReview
    ├── memory_patterns/         Working / Semantic / Episodic / Procedural memory pipelines
    │                            EpisodicMemoryRetriever, SemanticMemoryUpsert, SessionSummarizer
    ├── guardrails/              Input/OutputGuardrailGate, PiiRedactorCheck, FactCheckGate
    │                            Note: these specialisation knots predate the *Check convention;
    │                            they use the *Gate suffix and have not been renamed.
    │                            HallucinationDetector, CitationGrounder
    ├── structured_output/       JsonExtractor, YamlExtractor, PydanticValidator, EnumClassifier
    │                            SchemaEnforcer, RetryOnParseFailure, FormatCoercer
    ├── specialized_agents/      CodeAgent, SqlAgent, ResearchAgent, DataAnalystAgent, BrowserAgent
    ├── document_processing/     Ingestion, QA, Summarizer, Translation pipelines
    │                            EmbeddingIndexer, MetadataExtractor
    ├── chain_of_thought/        ChainOfThought, SelfConsistencyEnsemble, TreeOfThought,
    │                            StepBackPrompting
    ├── plan_and_execute/        TaskPlanner, PlanExecutor, PlanRevisor
    ├── reflection/              SelfCritiqueRevise, ConstitutionalFilter, OutcomeSimulator
    ├── tool_use/                ToolSelector, ParallelToolCaller, ToolChain,
    │                            ToolCallValidator, ToolResultFormatter
    ├── human_in_the_loop/       ApprovalCheck, ClarificationRequester, EscalationRouter
    ├── routing/                 IntentRouter, ConfidenceRouter, CapabilityRouter
    └── conversation/            MultiTurnContextAssembler, ConversationMemoryPruner
```

---

## The three interfaces

### LLMProvider

**Contract:** Implement three async methods. `chat` returns a raw response mapping; `stream_chat` yields raw chunk mappings; `close` releases connections and calls `_clear_credentials()` to null any stored API key.

**Must not:** Block the event loop. Both `chat` and `stream_chat` must be fully async. Never store credentials beyond `close()`.

```python
from pirn.core.providers.llm_provider import LLMProvider

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: str) -> None:
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._default_model = default_model
        self._config = api_key  # nulled by _clear_credentials()

    async def chat(self, messages, *, model=None, max_tokens=None, temperature=None):
        response = await self._client.messages.create(
            model=model or self._default_model,
            max_tokens=max_tokens or 1024,
            messages=list(messages),
        )
        return {"content": response.content[0].text, "stop_reason": response.stop_reason}

    async def stream_chat(self, messages, *, model=None, max_tokens=None, temperature=None):
        async with self._client.messages.stream(
            model=model or self._default_model,
            max_tokens=max_tokens or 1024,
            messages=list(messages),
        ) as stream:
            async for chunk in stream:
                yield {"delta": chunk}

    async def close(self) -> None:
        await self._client.close()
        self._clear_credentials()
```

---

### Tool / @tool decorator

**Contract:** Implement four members — `name` (stable string identifier), `description` (shown to the LLM during planning), `parameters_schema` (JSON Schema object), and `invoke(arguments)` (async, returns raw result). Exceptions raised by `invoke` are caught by `ToolExecutor` and surfaced as `ToolResult.error`; do not suppress them yourself.

**When to use `@tool` vs subclassing:** Use `@tool` for plain functions with no constructor dependencies. Use `Tool` subclassing when the tool needs injected API keys, HTTP clients, or connection pools.

```python
# @tool form — name, description, and schema derived automatically
from pirn.domains.agents import tool

@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return a summary of the top results."""
    ...  # your implementation

@tool
def lookup_policy(topic: str) -> str:
    """Look up an internal policy document by topic keyword."""
    return POLICIES.get(topic, "No policy found.")

# Subclass form — use when constructor injection is needed
from pirn.domains.agents.tool import Tool

class WebSearchTool(Tool):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web and return a list of result snippets."

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

    async def invoke(self, arguments):
        ...  # call your search API here

    def _clear_credentials(self) -> None:
        self._api_key = None
```

---

### MemoryStore

**Contract:** Implement five async methods. `store(key, value)` persists a mapping. `retrieve(key)` returns the mapping or `None`. `search(query, *, top_k)` async-iterates the `top_k` most similar entries. `forget(key)` removes an entry. `close()` releases connections and calls `_clear_credentials()`.

```python
from pirn.domains.agents.memory_store import MemoryStore
from collections.abc import AsyncIterator, Mapping
from typing import Any

class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._data: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self._data[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self._data.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        # Minimal stub — no similarity ranking
        async def _iter():
            for v in list(self._data.values())[:top_k]:
                yield v
        return _iter()

    async def forget(self, key: str) -> None:
        self._data.pop(key, None)

    async def close(self) -> None:
        self._data.clear()
        self._clear_credentials()
```

---

## Canonical pipeline chain

The 80% chain for a single-turn tool-using agent:
`MessageParser → ContextBuilder → LLMCall → OutputParser`

Safety and tool execution are inserted between `LLMCall` and `OutputParser`.

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.domains.agents.input.message_parser import MessageParser
from pirn.domains.agents.input.context_builder import ContextBuilder
from pirn.domains.agents.generation.llm_call import LLMCall
from pirn.domains.agents.generation.output_parser import OutputParser
from pirn.domains.agents.generation.response_formatter import ResponseFormatter
from pirn.domains.agents.control.safety_check import SafetyCheck

provider = AnthropicProvider(api_key="...", default_model="claude-sonnet-4-6")

async def main():
    with Tapestry() as t:
        raw      = Parameter("user_input", str)
        messages = MessageParser(raw_input=raw,      _config=KnotConfig(id="parse"))
        context  = ContextBuilder(
                       messages=messages,
                       system_prompt="You are a helpful assistant.",
                       _config=KnotConfig(id="ctx"),
                   )
        response = LLMCall(context=context, llm=provider, _config=KnotConfig(id="llm"))
        safe     = SafetyCheck(
                       message=response,
                       deny_patterns=[r"\b(ignore previous instructions)\b"],
                       _config=KnotConfig(id="safety"),
                   )
        parsed   = OutputParser(response=response,   _config=KnotConfig(id="out"))
        output   = ResponseFormatter(
                       response=parsed,
                       format="markdown",
                       _config=KnotConfig(id="fmt"),
                   )

    result = await t.run(RunRequest(parameters={"user_input": "Hello!"}))
    print(result.outputs["fmt"])
    await provider.close()

asyncio.run(main())
```

Note: `safe` is wired in parallel with `parsed` — both depend on `response`. If you need to block `parsed` on safety passing, wire `safe` as an upstream dependency of `parsed` via a guard knot.

---

## Control knots

These knots live in `control/` and return booleans. They are **not** `Gate` subclasses; they do not automatically block downstream knots. Wire their `bool` output to an upstream gate or handle it in the calling knot.

| Knot | Returns `True` when | Typical use |
|------|---------------------|-------------|
| `TerminationCheck` | `finish_reason == "stop"` or `current_iteration >= max_iterations` | Stop a manual iteration loop |
| `SafetyCheck` | No deny-list pattern matches the message/response content | Block unsafe content from entering or leaving the pipeline |
| `ReflectionCheck` | LLM scores the response quality at or above `threshold` | Self-critique loop: iterate until quality bar is met |
| `HandoffCheck` | Response matches any escalation pattern | Route to a human-in-the-loop or supervisor agent |

**Constructor notes:**
- `SafetyCheck` requires `deny_patterns` to be a sequence of non-empty regex strings; they are compiled at construction with `re.IGNORECASE`.
- `TerminationCheck` requires `max_iterations` (positive int) and `current_iteration` (knot or int; auto-coerced to `Parameter` when a plain int is supplied).

---

## ReActLoop (SubTapestry)

`ReActLoop` wraps an unrolled fixed-length chain of `ReActStepExecutor` knots, each guarded by `ReActTerminationCheck`. Runs that finish early pay the cost of a few short-circuit knots; they do not spin idle iterations.

**When to use it vs wiring manually:** Use `ReActLoop` whenever the agent may call tools zero or more times before producing a final answer. Wire manually only when you need step-level visibility in the outer tapestry graph or non-standard accumulation logic.

**Constructor:**

```python
ReActLoop(
    messages=...,           # Knot | tuple[AgentMessage] | list[AgentMessage]
    llm=provider,           # LLMProvider — required
    tools=[...],            # Sequence[Tool] — required, may be empty
    max_iterations=10,      # int > 0, default 10
    _config=KnotConfig(id="react"),
)
```

**Example — embed inside a larger tapestry:**

```python
from pirn.domains.agents.specializations.react.react_loop import ReActLoop

with Tapestry() as t:
    raw   = Parameter("task", str)
    react = ReActLoop(
        messages=[{"role": "user", "content": raw}],
        llm=provider,
        tools=[web_search, lookup_policy],
        max_iterations=6,
        _config=KnotConfig(id="react"),
    )

result = await t.run(RunRequest(parameters={"task": "Research CRISPR advances in 2025."}))
response: AgentResponse = result.outputs["react"]
```

---

## Human-in-the-loop patterns

Three knots in `specializations/human_in_the_loop/` handle points in a pipeline where a human (or a supervising agent) must intervene before execution continues.

| Knot | Purpose | Returns |
|------|---------|---------|
| `ApprovalCheck` | Emit an approval request for an `AgentResponse`; gate downstream execution on the result | `bool` — `True` if approved |
| `ClarificationRequester` | Detect ambiguous user messages via LLM; return a clarifying question or the original message | `str` |
| `EscalationRouter` | Pass high-confidence responses through; return `None` for low-confidence ones that need human review | `AgentResponse \| None` |

**Key points:**
- All three return plain values, not booleans that auto-block the graph. Wire their outputs to a `Gate` when you need to halt execution on failure.
- `ApprovalCheck` accepts `auto_approve=True` for non-production or test use — the request record is still emitted, but the knot always returns `True`.
- `EscalationRouter` reads `response.usage["confidence"]`; providers that do not populate this field will always escalate (confidence is treated as 0).

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.nodes.gate.gate import Gate
from pirn.domains.agents.generation.llm_call import LLMCall
from pirn.domains.agents.generation.output_parser import OutputParser
from pirn.domains.agents.input.context_builder import ContextBuilder
from pirn.domains.agents.input.message_parser import MessageParser
from pirn.domains.agents.specializations.human_in_the_loop.approval_check import ApprovalCheck
from pirn.domains.agents.specializations.human_in_the_loop.escalation_router import EscalationRouter

# provider defined elsewhere
async def main():
    with Tapestry() as t:
        raw      = Parameter("user_input", str)
        messages = MessageParser(raw_input=raw,      _config=KnotConfig(id="parse"))
        context  = ContextBuilder(messages=messages, _config=KnotConfig(id="ctx"))
        response = LLMCall(context=context, llm=provider, _config=KnotConfig(id="llm"))
        parsed   = OutputParser(response=response,   _config=KnotConfig(id="out"))

        # Route low-confidence responses to escalation (returns None when confidence < 0.8)
        routed   = EscalationRouter(
                       response=parsed,
                       threshold=0.8,
                       _config=KnotConfig(id="escalation_router"),
                   )
        # Gate blocks downstream knots when routed is None (escalation path)
        approved = Gate(
                       input=routed,
                       predicate=lambda v: v is not None,
                       _config=KnotConfig(id="escalation_gate"),
                   )

        # For responses that pass routing, require explicit approval before continuing
        approval = ApprovalCheck(
                       response=parsed,
                       _config=KnotConfig(id="approval"),
                   )
        Gate(
            input=approval,
            predicate=lambda approved: approved,
            _config=KnotConfig(id="approval_gate"),
        )

    result = await t.run(RunRequest(parameters={"user_input": "Summarise our Q3 financials."}))
```

---

## Plan-and-execute pattern

Three knots in `specializations/plan_and_execute/` decompose a high-level goal into an ordered plan, execute it step by step, and optionally revise the remaining steps when a step fails.

| Knot | Purpose | Input → Output |
|------|---------|----------------|
| `TaskPlanner` | Ask the LLM to decompose a goal into ordered steps | `goal: str` → `Plan` |
| `PlanExecutor` | Execute each step sequentially, feeding prior results as context | `plan: Plan` → `AgentResponse` |
| `PlanRevisor` | Given partial results and a failure reason, ask the LLM to rewrite the remaining steps | `original_plan, completed_results, failure_reason` → `Plan` |

**Key points:**
- `PlanExecutor` runs steps sequentially inside its own loop — it is not a `LoopSubTapestry`. All steps share the same `LLMProvider` call context.
- `PlanRevisor` is optional. Use it when you want the agent to self-correct a stalled plan rather than failing the whole pipeline.
- `TaskPlanner` parses numbered lines (`1. step one`) from the LLM response. Lines starting with `#` are treated as rationale and excluded from `Plan.steps`.

```python
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.domains.agents.specializations.plan_and_execute.task_planner import TaskPlanner
from pirn.domains.agents.specializations.plan_and_execute.plan_executor import PlanExecutor

# provider defined elsewhere
async def main():
    with Tapestry() as t:
        goal     = Parameter("goal", str)
        plan     = TaskPlanner(
                       goal=goal,
                       llm=provider,
                       _config=KnotConfig(id="planner"),
                   )
        result   = PlanExecutor(
                       plan=plan,
                       llm=provider,
                       _config=KnotConfig(id="executor"),
                   )

    run = await t.run(RunRequest(parameters={
        "goal": "Write a market analysis report for solar energy in Texas."
    }))
    print(run.outputs["executor"].content)
    await provider.close()
```

To add revision on failure, wire `PlanRevisor` with `ErrorPolicy.RECEIVE_ERRORS` on `PlanExecutor`:

```python
from pirn.core.error_policy import ErrorPolicy
from pirn.domains.agents.specializations.plan_and_execute.plan_revisor import PlanRevisor

with Tapestry() as t:
    goal     = Parameter("goal", str)
    plan     = TaskPlanner(goal=goal, llm=provider, _config=KnotConfig(id="planner"))
    executed = PlanExecutor(
                   plan=plan, llm=provider,
                   _config=KnotConfig(id="executor", error_policy=ErrorPolicy.RECEIVE_ERRORS),
               )
    PlanRevisor(
        original_plan=plan,
        completed_results="",
        failure_reason=executed,      # Err result passed through when executor fails
        llm=provider,
        _config=KnotConfig(id="revisor", error_policy=ErrorPolicy.RECEIVE_ERRORS),
    )
```

---

## Anti-patterns

### Passing a Plan directly to ToolRouter

`ToolRouter` accepts a **step string**, not a `Plan`. Feed it the `Plan` directly and it will fail or silently coerce the entire plan object to a string and match nothing. Extract the step first:

```python
# Wrong
router = ToolRouter(step=plan_knot, tools=tools, _config=...)

# Correct — extract the step string you want first
class PlanFirstStep(Knot):
    async def process(self, plan: Plan, **_) -> str:
        return plan.steps[0] if plan.steps else ""

step   = PlanFirstStep(plan=plan_knot, _config=KnotConfig(id="step"))
router = ToolRouter(step=step, tools=tools, _config=KnotConfig(id="route"))
```

### Confusing *Check knots with Gate

`SafetyCheck`, `TerminationCheck`, `ReflectionCheck`, and `HandoffCheck` return a `bool`; they do not branch the graph or prevent downstream knots from executing. They are inputs to gates, not gates themselves. To actually block execution, feed the `bool` output into a `Gate` knot or handle it in the next knot's `process` method.

### Implementing LLMProvider synchronously

`chat` and `stream_chat` must be `async`. A synchronous implementation blocks the event loop and will stall all other knots running concurrently in the tapestry. Wrap blocking SDKs with `asyncio.to_thread` at minimum; prefer async SDKs.

### Holding credentials beyond close()

Call `self._clear_credentials()` inside `close()` for every provider, tool, or store that holds an API key or token. Skipping this keeps the credential string reachable for the lifetime of the object reference — a violation of the pirn no-leak principle.

### Using MemoryRetriever and expecting a hard failure on a miss

`MemoryRetriever` raises `KeyError` on a cache miss by design (fail-loud). Do not assume it returns `None`. Wrap calls in a gate or a fallback knot when a miss is a valid path.

---

## Constraints and gotchas

- **No concrete implementations ship with pirn.** For local testing copy `StubLLMProvider`, `StubMemoryStore`, and `StubTool` from `tests/unit/domains/agents/conftest.py`.
- **`ToolRouter` matches by substring.** It finds the first tool whose `name` appears anywhere in the step string (case-insensitive). Tool names must be distinct substrings; short names like `"get"` risk false matches.
- **`ReActLoop` is fixed-length at build time.** `max_iterations` sets the number of step knots wired in the inner tapestry. Changing it after construction has no effect.
- **`StreamingLLMCall` does not consume the stream.** The knot returns the `AsyncIterator` directly. The caller owns iteration and must exhaust the iterator to avoid resource leaks.
- **Scalar auto-coercion.** Any knot parameter typed `Knot | T` (e.g. `step: Knot | str`) accepts a plain scalar. The framework wraps it in a `Parameter` node automatically — no manual wrapping needed.
- **`ResponseFormatter` format options are `"plain"`, `"markdown"`, and `"json"`.** Any other value raises at construction.
- **`OutputParser` recognises two wire shapes.** Anthropic (`content` / `stop_reason`) and OpenAI (`choices[0].message`). Custom provider responses that use neither shape will produce an empty `AgentResponse.content`.

---

## Quick reference

| Task | How |
|------|-----|
| Parse raw user text | `MessageParser(raw_input=..., _config=...)` |
| Build conversation context | `ContextBuilder(messages=..., system_prompt=..., _config=...)` |
| Call an LLM (blocking) | `LLMCall(context=..., llm=provider, _config=...)` |
| Call an LLM (streaming) | `StreamingLLMCall(context=..., llm=provider, _config=...)` |
| Parse raw response to typed object | `OutputParser(response=..., _config=...)` |
| Format response for display | `ResponseFormatter(response=..., format="markdown", _config=...)` |
| Deny-list safety gate | `SafetyCheck(message=..., deny_patterns=[...], _config=...)` |
| Stop an iteration loop | `TerminationCheck(response=..., max_iterations=N, current_iteration=..., _config=...)` |
| Produce an explicit plan | `Planner(context=..., llm=provider, _config=...)` |
| Route a plan step to a tool | `PlanFirstStep → ToolRouter(step=..., tools=[...], _config=...)` |
| Execute a tool call | `ToolExecutor(call=router_knot, tools=[...], _config=...)` |
| Reason+act loop with tools | `ReActLoop(messages=..., llm=..., tools=[...], max_iterations=N, _config=...)` |
| Write to memory | `MemoryWriter(key=..., value=..., memory_store=store, _config=...)` |
| Retrieve from memory | `MemoryRetriever(query=..., memory_store=store, _config=...)` |
| Sliding message window | `ConversationBuffer(messages=..., max_turns=N, _config=...)` |
| RAG (simple) | `NaiveRagPipeline(query=..., memory_store=..., llm=..., top_k=5, _config=...)` |
| RAG (self-correcting) | `SelfRAG(query=..., memory_store=..., llm=..., _config=...)` |
| RAG (multi-hop) | `MultiHopRAG(query=..., memory_store=..., llm=..., hops=3, _config=...)` |
| Rerank retrieved docs | `Reranker(candidates=..., query=..., llm=..., _config=...)` |
| Structured output (Pydantic) | `PydanticValidatorPipeline(response=..., schema=MyModel, llm=..., _config=...)` |
| Enforce JSON schema strictly | `SchemaEnforcer(response=..., schema=..., _config=...)` |
| Retry on parse failure | `RetryOnParseFailure(response=..., parser=..., llm=..., max_retries=3, _config=...)` |
| Multi-agent fan-out | `ParallelSpecialistFanOut(task=..., specialists={...}, _config=...)` |
| Round-robin review | `RoundRobinReview(draft=..., reviewers=[...], _config=...)` |
| Decentralised swarm handoff | Implement `Knot.process` to call `get_current_store().register(next_agent)` |
| Chain-of-thought reasoning | `ChainOfThought(context=..., llm=..., _config=...)` |
| Self-consistency ensemble | `SelfConsistencyEnsemble(context=..., llm=..., samples=5, _config=...)` |
| Tree-of-thought search | `TreeOfThought(context=..., llm=..., branching=3, depth=3, _config=...)` |
| Step-back prompting | `StepBackPrompting(context=..., llm=..., _config=...)` |
| Plan then execute | `TaskPlanner(context=..., llm=..., _config=...) → PlanExecutor(plan=..., tools=[...], _config=...)` |
| Revise a stale plan | `PlanRevisor(plan=..., feedback=..., llm=..., _config=...)` |
| Self-critique + revise | `SelfCritiqueRevise(response=..., llm=..., _config=...)` |
| Constitutional filtering | `ConstitutionalFilter(response=..., principles=[...], llm=..., _config=...)` |
| Select the right tool | `ToolSelector(context=..., tools=[...], llm=..., _config=...)` |
| Call tools in parallel | `ParallelToolCaller(calls=..., tools=[...], _config=...)` |
| Validate tool call args | `ToolCallValidator(call=..., tools=[...], _config=...)` |
| Human approval gate | `ApprovalCheck(request=..., approver=..., _config=...)` |
| Request clarification | `ClarificationRequester(context=..., llm=..., _config=...)` |
| Escalation routing | `EscalationRouter(response=..., rules=[...], _config=...)` |
| Route by intent | `IntentRouter(context=..., routes={...}, _config=...)` |
| Route by confidence | `ConfidenceRouter(response=..., threshold=0.8, fallback=..., _config=...)` |
| Assemble multi-turn context | `MultiTurnContextAssembler(history=..., max_tokens=N, _config=...)` |
| Prune conversation memory | `ConversationMemoryPruner(messages=..., max_turns=N, _config=...)` |
| Persist episodic memory | `EpisodicMemoryRetriever(event=..., memory_store=store, _config=...)` |
| Upsert semantic memory | `SemanticMemoryUpsert(content=..., memory_store=store, _config=...)` |
| Summarise session | `SessionSummarizer(messages=..., llm=..., _config=...)` |
| Detect hallucinations | `HallucinationDetector(response=..., sources=..., llm=..., _config=...)` |
| Ground citations | `CitationGrounder(response=..., documents=..., _config=...)` |
| Index documents for embedding | `EmbeddingIndexer(documents=..., memory_store=store, _config=...)` |
| Extract document metadata | `MetadataExtractor(document=..., llm=..., _config=...)` |

---

*See also: [pirn AGENTIC_USE.md](../../../AGENTIC_USE.md)*
