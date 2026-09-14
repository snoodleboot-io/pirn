# AGENTIC_USE — pirn_agents

This domain provides knots and interfaces for building LLM-backed pipelines in pirn; it does **not** ship any concrete LLM, vector-store, or tool implementations — those are always user-supplied.

---

## Mental model

Agent behaviour in pirn is expressed as an ordinary knot graph built from core's
own vocabulary: `Knot`, `SubTapestry`, `LoopSubTapestry` (for the patterns whose
reasoning genuinely repeats), `Result` (`Ok | Err | Skipped`), and `Payload`.
There is no hidden runtime loop; the agent loop *is* your pipeline. This
domain's knots cover the lifecycle in five sub-packages — **Input** (parse raw
text, classify intent, build a conversation window), **Generation** (call an
LLM, parse and format the response), **Planning** (produce a plan, route steps
to tools, execute and aggregate results), **Memory** (write and retrieve
conversation state), and **Control** (gate iteration, enforce safety, detect
termination or escalation) — sometimes still called the agent "tiers" in
conversation, though that word names no class or contract.

The three things you must supply are a concrete **LLMProvider**, one or more **Tool** implementations, and optionally a **MemoryStore**. Every agent knot depends only on these interfaces; pirn never imports a vendor SDK directly. This keeps `pirn-agents` free of heavy mandatory dependencies and your application free to choose any backend.

All three interfaces inherit from `PirnOpaqueValue`. pirn serialises them by identity rather than by inspecting their internals, so content-addressing cache stays stable even when providers hold live SDK state or open connections.

---

## Install

```bash
pip install pirn-agents

# Add your chosen LLM provider SDK separately:
pip install anthropic          # Anthropic
pip install openai             # OpenAI-compatible APIs

# If you need a vector store for memory:
pip install pinecone-client    # or qdrant-client, weaviate-client, etc.
```

---

## Source map

```
pirn_agents/
├── llm/
│   └── llm_provider.py          LLMProvider           — interface you must implement
├── tools/
│   ├── tool.py                  Tool                  — interface you must implement (a Knot class)
│   └── tool_decorator.py        @ToolDecorator.decorate / FunctionTool  — shorthand for plain functions
├── memory/stores/
│   └── memory_store.py          MemoryStore           — interface you must implement
├── types/messaging/
│   ├── agent_message.py         AgentMessage          — single conversation turn
│   ├── conversation_payload.py  ConversationPayload   — Payload[ConversationFrame, tuple[AgentMessage, ...]]
│   ├── conversation_frame.py    ConversationFrame     — session/turn ids, token count, truncation state
│   ├── agent_response.py        AgentResponse         — Payload[GenerationFrame, str]
│   └── generation_frame.py      GenerationFrame       — finish_reason, usage, cost, tool_calls
├── planning/plan.py             Plan                  — ordered tuple of step strings
├── tools/tool_call.py           ToolCall              — LLM-requested tool invocation
├── tools/tool_result.py         ToolResult            — the model-facing view of a ToolCall's Result
├── input/
│   ├── message_parser.py        MessageParser         — raw input → AgentMessage tuple
│   ├── context_builder.py       ContextBuilder        — messages + system_prompt → ConversationPayload
│   └── intent_classifier.py     IntentClassifier      — context → intent label string
├── generation/
│   ├── llm_call.py              LLMCall               — ConversationPayload → raw response mapping
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
    │                            SelfRAGPipeline, AdaptiveRAGPipeline, MultiHopRAGPipeline, Reranker, RAGSynthesizer
    ├── multi_agent/             OrchestratorAgent, ParallelSpecialistFanOut, DebateFramework,
    │                            ConsensusPipeline, RoundRobinReview
    ├── memory_patterns/         Working / Semantic / Episodic / Procedural memory pipelines
    │                            EpisodicMemoryRetriever, SemanticMemoryUpsert, SessionSummarizer
    ├── guardrails/              Input/OutputGuardrailCheck, PiiRedactorCheck, FactCheck
    │                            HallucinationDetector, CitationGrounder
    ├── structured_output/       JsonExtractor, YamlExtractor, PydanticValidator, EnumClassifier
    │                            SchemaEnforcer, RetryOnParseFailure, FormatCoercer
    ├── specialized_agents/      CodeAgent, SQLAgent, ResearchAgent, DataAnalystAgent, BrowserAgent
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
from pirn_agents.llm.llm_provider import LLMProvider

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

### Tool / @ToolDecorator.decorate decorator

**Contract:** A `Tool` is a `Knot` subclass — the capability is the class, one
call is an instance built with `KnotConfig(id=call_id)` plus the call's
arguments as inputs, and the outcome is the engine's `Ok | Err | Skipped` plus
the run's `KnotLineage` row. `name`/`description`/`parameters` are derived
from `process()`'s own type hints (`declaration()`), not hand-written
properties; there is no second execution verb — `process()` **is** how a tool
runs. A dependency a call never supplies — an API key, an HTTP client, a
connection pool — is bound once with `bind()`, which hides it from the
model's declaration.

**When to use `@ToolDecorator.decorate` vs subclassing:** Use `@ToolDecorator.decorate` for plain functions with
no bound dependencies. Use `Tool` subclassing when the tool needs an injected
API key, HTTP client, or connection pool via `bind()`.

```python
# @ToolDecorator.decorate form — name, description, and schema derived automatically
from pirn_agents.tools.tool_decorator import ToolDecorator

@ToolDecorator.decorate
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return a summary of the top results."""
    ...  # your implementation

@ToolDecorator.decorate
def lookup_policy(topic: str) -> str:
    """Look up an internal policy document by topic keyword."""
    return POLICIES.get(topic, "No policy found.")

# Subclass form — use when constructor injection is needed
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.tools.tool import Tool

class WebSearchTool(Tool):
    tool_name: ClassVar[str] = "web_search"
    tool_description: ClassVar[str] = "Search the web and return a list of result snippets."

    def __init__(
        self, *, query: Knot | str, client: Knot, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(query=query, client=client, _config=_config, **kwargs)

    async def process(self, query: str, client: Any, **_: Any) -> list[dict[str, str]]:
        return await client.search(query)  # call your search API here

# `client` is a dependency a call never supplies, so it is bound once and
# hidden from the model's declaration:
web_search_tool = WebSearchTool.bind(client=my_client)
```

---

### MemoryStore

**Contract:** Implement five async methods. `store(key, value)` persists a mapping. `retrieve(key)` returns the mapping or `None`. `search(query, *, top_k)` async-iterates the `top_k` most similar entries. `forget(key)` removes an entry. `close()` releases connections and calls `_clear_credentials()`.

```python
from pirn_agents.memory.stores.memory_store import MemoryStore
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
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_agents.input.message_parser import MessageParser
from pirn_agents.input.context_builder import ContextBuilder
from pirn_agents.generation.llm_call import LLMCall
from pirn_agents.generation.output_parser import OutputParser
from pirn_agents.generation.response_formatter import ResponseFormatter
from pirn_agents.control.safety_check import SafetyCheck

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
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.messaging.agent_message import AgentMessage

with Tapestry() as t:
    react = ReActLoop(
        messages=(AgentMessage(role="user", content="Research CRISPR advances in 2025."),),
        llm=provider,
        tools=[web_search, lookup_policy],
        max_iterations=6,
        _config=KnotConfig(id="react"),
    )

result = await t.run(RunRequest())
response: AgentResponse = result.outputs["react"]   # Payload[GenerationFrame, str]
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
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn.nodes.gate.gate import Gate
from pirn_agents.generation.llm_call import LLMCall
from pirn_agents.generation.output_parser import OutputParser
from pirn_agents.input.context_builder import ContextBuilder
from pirn_agents.input.message_parser import MessageParser
from pirn_agents.specializations.human_in_the_loop.approval_check import ApprovalCheck
from pirn_agents.specializations.human_in_the_loop.escalation_router import EscalationRouter

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
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_agents.specializations.plan_and_execute.task_planner import TaskPlanner
from pirn_agents.specializations.plan_and_execute.plan_executor import PlanExecutor

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
from pirn_agents.specializations.plan_and_execute.plan_revisor import PlanRevisor

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

Every entry below was checked against the real `__init__` signature (grep it yourself with `grep -n "def __init__" -A8 <file>` if in doubt — the "Source map" above and `PATTERNS.md` name the file for each class).

| Task | How |
|------|-----|
| Parse raw user text | `MessageParser(raw_input=..., _config=...)` |
| Build conversation window | `ContextBuilder(messages=..., system_prompt=..., _config=...)` |
| Call an LLM (blocking) | `LLMCall(context=..., llm=provider, _config=...)` |
| Call an LLM (streaming) | `StreamingLLMCall(context=..., llm=provider, _config=...)` |
| Parse raw response to typed object | `OutputParser(response=..., _config=...)` |
| Format response for display | `ResponseFormatter(response=..., format="markdown", _config=...)` |
| Deny-list safety gate | `SafetyCheck(message=..., deny_patterns=[...], _config=...)` |
| Stop an iteration loop | `TerminationCheck(response=..., max_iterations=N, current_iteration=..., _config=...)` |
| Produce an explicit plan | `Planner(context=..., llm=provider, _config=...)` |
| Route a plan step to a tool | `PlanFirstStep → ToolRouter(step=..., tools=[...], _config=...)` |
| Execute a tool call | `ToolExecutor(call=router_knot, tools=[...], _config=...)` |
| Reason+act loop with tools | `ReActLoop(messages=(...,), llm=..., tools=[...], max_iterations=N, _config=...)` |
| Write to memory | `MemoryWriter(key=..., value=..., store=store, _config=...)` |
| Retrieve from memory (by key) | `MemoryRetriever(key=..., store=store, _config=...)` — raises `KeyError` on a miss; similarity search is `store.search(query, top_k=...)` directly, no wrapping knot |
| Sliding message window | `ConversationBuffer(new_message=..., history=(...,), max_size=N, _config=...)` — appends one message per call, not a static list |
| RAG (simple) | `NaiveRAGPipeline(query=..., memory=..., llm=..., top_k=5, _config=...)` |
| RAG (self-correcting) | `SelfRAGPipeline(query=..., memory=..., llm=..., top_k=5, _config=...)` |
| RAG (multi-hop) | `MultiHopRAGPipeline(query=..., memory=..., llm=..., top_k=5, num_hops=3, _config=...)` |
| Rerank retrieved docs | `Reranker(query=..., documents=..., llm=..., reranker=..., top_k=5, _config=...)` |
| Structured output (Pydantic) | `PydanticValidatorPipeline(prompt=..., llm=..., model_class=MyModel, max_retries=3, _config=...)` |
| Enforce JSON schema strictly | `SchemaEnforcer(response=..., model_class=..., _config=...)` |
| Retry on parse failure | `RetryOnParseFailure(prompt=..., llm=..., parser=..., max_retries=3, _config=...)` |
| Multi-agent fan-out | `ParallelSpecialistFanOut(task=..., specialists={...}, _config=...)` |
| Round-robin review | `RoundRobinReview(response=..., reviewers=[...], _config=...)` |
| Decentralised swarm handoff | Implement `Knot.process` to call `Tapestry.current_store().register(next_agent)` |
| Chain-of-thought reasoning | `ChainOfThought(prompt=..., llm=..., _config=...)` |
| Self-consistency ensemble | `SelfConsistencyEnsemble(prompt=..., llm=..., samples=5, _config=...)` |
| Tree-of-thought search | `TreeOfThought(prompt=..., llm=..., k_candidates=3, beam_width=2, depth=3, _config=...)` |
| Step-back prompting | `StepBackPrompting(prompt=..., llm=..., _config=...)` |
| Plan then execute | `TaskPlanner(goal=..., llm=..., _config=...) → PlanExecutor(plan=..., llm=..., _config=...)` |
| Revise a stale plan | `PlanRevisor(original_plan=..., completed_results=..., failure_reason=..., llm=..., _config=...)` |
| Self-critique + revise | `SelfCritiqueRevise(prompt=..., llm=..., _config=...)` |
| Constitutional filtering | `ConstitutionalFilter(response=..., principles=[...], llm=..., max_revisions=3, _config=...)` |
| Select the right tool | `ToolSelector(message=..., tools=[...], llm=..., _config=...)` |
| Call tools in parallel | `ParallelToolCaller(tool_calls=[...], tools=[...], _config=...)` |
| Validate tool call args | `ToolCallValidator(tool_call=..., tools=[...], _config=...)` |
| Human approval gate | `ApprovalCheck(response=..., auto_approve=False, _config=...)` |
| Request clarification | `ClarificationRequester(message=..., llm=..., _config=...)` |
| Escalation routing | `EscalationRouter(response=..., threshold=0.8, _config=...)` |
| Route by intent | `IntentRouter(message=..., llm=..., categories=[...], _config=...)` |
| Route by confidence | `ConfidenceRouter(score=..., threshold=0.8, _config=...)` |
| Assemble multi-turn context | `MultiTurnContextAssembler(messages=(...,), max_turns=10, max_tokens=4000, _config=...)` |
| Prune conversation memory | `ConversationMemoryPruner(messages=..., token_budget=50, _config=...)` |
| Retrieve episodic memory | `EpisodicMemoryRetriever(context=..., store=store, top_k=5, _config=...)` |
| Upsert semantic memory | `SemanticMemoryUpsert(response=..., llm=..., store=store, _config=...)` |
| Summarise session | `SessionSummarizer(messages=..., llm=..., token_threshold=2000, _config=...)` |
| Detect hallucinations | `HallucinationDetector(response=..., sources=..., llm=..., _config=...)` |
| Ground citations | `CitationGrounder(response=..., sources=..., llm=..., _config=...)` |
| Index documents for embedding | `EmbeddingIndexer(chunks=..., embedding_provider=..., store=store, _config=...)` |
| Extract document metadata | `MetadataExtractor(document=..., llm=..., _config=...)` |

---

*See also: [pirn AGENTIC_USE.md](../../../AGENTIC_USE.md)*

---

## Agentic RAG patterns (F9)

The full agentic-RAG taxonomy — see
[`specializations/rag/RETRIEVAL_TAXONOMY.md`](specializations/rag/RETRIEVAL_TAXONOMY.md)
for the axes, knot map, and F4 dependency notes. Each pattern runs on
`InMemoryVectorStore` with no external service.

### Query transformation
| Task | Wiring |
| ---- | ------ |
| Multi-query + RRF fusion | `RagFusionPipeline(query=..., memory=store, llm=llm, num_queries=4, _config=...)` |
| Decompose into sub-questions | `SubQuestionRagPipeline(query=..., memory=store, llm=llm, max_sub_questions=4, _config=...)` |
| Self-query metadata filter | `SelfQueryRagPipeline(query=..., store=vector_store, embedder=..., llm=llm, _config=...)` |
| FLARE active retrieval | `FlareActiveRagPipeline(query=..., memory=store, llm=llm, confidence_threshold=0.5, _config=...)` |

### Retrieval strategy
| Task | Wiring |
| ---- | ------ |
| Route to best index | `RouterRagPipeline(query=..., routes=RouteTable({...}), llm=llm, _config=...)` |
| Agentic RAG (retrieval-as-tool) | `AgenticRagPipeline(query=..., rag_tool=RagTool(...), llm=llm, max_iterations=3, _config=...)` |
| Iterative / recursive retrieve | `IterativeRetriever(query=..., memory=store, llm=llm, max_iterations=3, _config=...)` |
| Speculative draft-then-verify | `SpeculativeRagPipeline(query=..., memory=store, llm=llm, _config=...)` |

### Post-retrieval
| Task | Wiring |
| ---- | ------ |
| Contextual retrieval + rerank + compress | `ContextualRetrievalPipeline(query=..., memory=store, llm=llm, reranker=backend, _config=...)` |
| Enrich chunk with context | `ContextualChunkEnricher(documents=..., document_text=..., llm=llm, _config=...)` |
| Compress retrieved context | `ContextualCompressor(query=..., documents=..., llm=llm, _config=...)` |

### Indexing structure (extends `document_processing/`)
| Task | Wiring |
| ---- | ------ |
| Parent-doc / small-to-big | `ParentDocumentIngestor(...)` + `ParentDocumentRetriever(...)` |
| Sentence-window | `SentenceWindowIngestor(...)` + `SentenceWindowRetriever(...)` |
| Auto-merging | `AutoMergingIngestor(...)` + `AutoMergingRetriever(...)` |
| RAPTOR hierarchical tree | `RaptorTreeBuilder(...)` + `RaptorRetriever(...)` |
