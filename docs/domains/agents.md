# Agents domain

The agents domain (`pirn/domains/agents/`) provides a library of knots and interfaces for building LLM-backed pipelines in pirn. Every piece of agent behaviour — prompting, streaming, memory, planning, tool execution, control flow, and output parsing — is expressed as an ordinary knot that wires into a tapestry like any other. There is no hidden loop runtime: the agent loop is just your pipeline graph.

```bash
pip install pirn[agents]
```

The `agents` extra carries no heavy dependencies of its own. LLM providers, vector stores, and tool implementations are user-supplied; pirn only defines the interfaces they must satisfy.

---

## Overview

A typical agent pipeline in pirn has five tiers:

| Tier | Purpose | Sub-package |
|------|---------|-------------|
| Input | Parse raw user text, classify intent, build context | `input/` |
| Generation | Call an LLM (blocking or streaming), parse the response | `generation/` |
| Planning | Ask the LLM to produce an ordered plan, route and execute tools | `planning/` |
| Memory | Write conversation turns and retrieve relevant history | `memory/` |
| Control | Gate iteration, enforce safety, detect termination or handoff | `control/` |

Specialised pipelines (RAG, ReAct, document processing, multi-agent, structured output) live under `specializations/` as `SubTapestry`-based pre-built patterns.

---

## Core interfaces

### LlmProvider

`LLMProvider` (`pirn/domains/agents/llm_provider.py`) is the interface every LLM backend must satisfy. Inherit from it and implement the three async methods:

| Method | Signature | Description |
|--------|-----------|-------------|
| `chat` | `(messages, *, model, max_tokens, temperature) -> Mapping[str, Any]` | Blocking chat completion. Returns the raw provider response mapping. |
| `stream_chat` | `(messages, *, model, max_tokens, temperature) -> AsyncIterator[Mapping[str, Any]]` | Streamed chat completion. Yields raw chunk mappings as they arrive. |
| `close` | `() -> None` | Release underlying connections. Call `_clear_credentials()` here to null any API key reference. |

`messages` follows the standard role/content wire format used by both Anthropic and OpenAI-compatible APIs: a sequence of `{"role": "...", "content": "..."}` mappings.

`LLMProvider` inherits from `PirnOpaqueValue`, so pirn serialises providers by identity rather than by inspecting their internals. This keeps content-addressing cache stable even when the provider holds live SDK state.

```python
from pirn.domains.agents.llm_provider import LLMProvider

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, default_model: str) -> None:
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._default_model = default_model
        self._config = api_key  # cleared by _clear_credentials()

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

### Tool

`Tool` (`pirn/domains/agents/tool.py`) is the interface for any capability an agent can call during planning. Inherit from it and implement four members:

| Member | Kind | Description |
|--------|------|-------------|
| `name` | property → `str` | Stable identifier the agent addresses the tool by. |
| `description` | property → `str` | Human-readable description shown to the LLM when building a plan. |
| `parameters_schema` | property → `Mapping[str, Any]` | JSON Schema describing accepted arguments. |
| `invoke` | async method | Execute the tool with `arguments` and return the raw result. |

Tools are passed as config values to knots that use them (e.g. `ToolRouter`, `ToolExecutor`). Like providers, tools are treated as opaque by pirn's content-addressing.

```python
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
        # call your search API here
        return [{"title": "...", "snippet": "..."}]

    def _clear_credentials(self) -> None:
        self._api_key = None
```

For plain functions, use the `@tool` decorator instead of subclassing. It derives `name` from the function name, `description` from the docstring's first paragraph, and `parameters_schema` from type annotations. Both sync and async functions are accepted.

```python
from pirn.domains.agents import tool

@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return a summary of the top results."""
    ...  # your implementation

@tool
def lookup_policy(topic: str) -> str:
    """Look up an internal policy document by topic keyword."""
    return POLICIES.get(topic, "No policy found.")

# Pass directly anywhere Tool is accepted
react = ReActLoop(messages=msgs, llm=provider, tools=[web_search, lookup_policy], ...)
```

`@tool` produces a `FunctionTool` instance, which is a `Tool` subclass. Use `Tool` subclassing directly when the tool needs constructor-injected dependencies (API keys, HTTP clients, connection pools).

### MemoryStore

`MemoryStore` (`pirn/domains/agents/memory_store.py`) is the interface for keyed storage with optional similarity search. Inherit from it and implement:

| Method | Description |
|--------|-------------|
| `store(key, value)` | Persist an arbitrary mapping under `key`. |
| `retrieve(key)` | Return the mapping previously stored, or `None`. |
| `search(query, *, top_k)` | Async-iterate the `top_k` entries most similar to `query`. |
| `forget(key)` | Remove the entry stored under `key` if present. |
| `close()` | Release underlying connections. |

Concrete implementations may wrap a vector database (Pinecone, Weaviate, Qdrant), a document store, an in-memory dict, or a hybrid. The interface deliberately separates exact key retrieval from similarity search so callers can implement either or both.

---

## Sub-packages

### `input/`

Knots that sit at the boundary between raw user input and the typed agent pipeline.

| Knot | Description |
|------|-------------|
| `MessageParser` | Coerces raw strings, mappings, `AgentMessage` instances, or sequences of these into a `tuple[AgentMessage, ...]`. Fails fast on untyped input so nothing unverified enters the pipeline. |
| `ContextBuilder` | Assembles a tuple of messages plus an optional system prompt into an `AgentContext`. If `system_prompt` is provided it is prepended as a `system`-role message. |
| `IntentClassifier` | Uses an `LLMProvider` to classify the user's intent from the current context. Returns a string label. |

### `generation/`

Knots that call an `LLMProvider` and parse the response.

| Knot | Description |
|------|-------------|
| `LLMCall` | Non-streaming chat completion. Accepts an `AgentContext` and an `LLMProvider` config value; returns the raw response mapping. |
| `StreamingLLMCall` | Streaming chat completion. Returns an `AsyncIterator[Mapping[str, Any]]` of raw chunk mappings; the knot does not consume the stream so callers retain full control. |
| `OutputParser` | Parses a raw chat-completion mapping into a typed `AgentResponse`. Recognises both Anthropic (`content` / `stop_reason`) and OpenAI (`choices[0].message`) shapes. Tool-call entries are surfaced as `ToolCall` objects. |
| `ResponseFormatter` | Renders an `AgentResponse` into a display string. Supports `"plain"` (content only), `"markdown"` (tool calls in fenced blocks), and `"json"` (full audit dict). |

### `planning/`

Knots that handle tool-use reasoning.

| Knot | Description |
|------|-------------|
| `Planner` | Asks an `LLMProvider` for an ordered `Plan` grounded in the current `AgentContext`. Lines starting with `#` are treated as rationale; everything else becomes a numbered step in the `Plan`. |
| `ToolRouter` | Accepts a single plan step string and a sequence of `Tool`s. Matches the first tool whose `name` appears as a substring of the step (case-insensitive) and returns a `ToolCall`. |
| `ToolExecutor` | Accepts a `ToolCall` and a sequence of `Tool`s. Invokes the matching tool with `ToolCall.arguments` and returns a `ToolResult`. Exceptions are caught and surfaced as `ToolResult.error` so callers can decide how to react. |
| `ToolResultAggregator` | Collects a sequence of `ToolResult`s into a `{call_id: result}` mapping, ready to splice into the conversation context. |

### `memory/`

Knots for persisting and retrieving conversation state.

| Knot | Description |
|------|-------------|
| `MemoryWriter` | Persists a `(key, value)` entry to a `MemoryStore`. Returns `key` so downstream knots can address the just-written entry. |
| `MemoryRetriever` | Fetches the value stored under `key` from a `MemoryStore`. Raises `KeyError` on a miss so callers fail loudly. |
| `ConversationBuffer` | Maintains a sliding window of messages by appending new turns and truncating from the front when the buffer exceeds `max_turns`. |

### `control/`

Knots that decide whether the agent loop should continue, terminate, escalate, or be blocked.

| Knot | Description |
|------|-------------|
| `TerminationCheck` | Returns `True` when the response carries `finish_reason="stop"` or when `current_iteration >= max_iterations`. Wire downstream knots to the gate's output to stop iterating. |
| `ReflectionCheck` | Asks an `LLMProvider` whether the current response is good enough to stop. The LLM is prompted to answer `"yes"` (iterate) or `"no"` (stop). |
| `SafetyCheck` | Checks the message or response body against a deny-list of regex patterns compiled with `re.IGNORECASE`. Returns `True` if no pattern matches (safe to proceed). |
| `HandoffCheck` | Returns `True` when the response matches any escalation pattern. Wire to a human-in-the-loop or supervisor agent knot. |

### `specializations/`

Pre-built `SubTapestry` pipelines for common agent patterns.

| Sub-area | Pipelines |
|----------|-----------|
| `rag/` | `NaiveRagPipeline`, `CorrectiveRagPipeline`, `HydeRagPipeline`, `GraphRagPipeline` — retrieval-augmented generation patterns with relevance gating |
| `react/` | `ReActLoop` — Reasoning + Acting loop with step accumulation, tool execution, and termination gating |
| `document_processing/` | `DocumentIngestionPipeline`, `DocumentQAPipeline`, `DocumentSummarizerPipeline`, `DocumentTranslationPipeline` |
| `multi_agent/` | `OrchestratorAgent`, `ParallelSpecialistFanOut`, `DebateFramework`, `ConsensusAggregator` — multi-agent coordination patterns |
| `guardrails/` | Input/output guardrail gates, PII redaction, fact-checking |
| `structured_output/` | `JsonExtractorPipeline`, `YamlExtractorPipeline`, `PydanticValidatorPipeline`, `EnumClassifierPipeline` |
| `memory_patterns/` | Working memory, episodic memory, semantic memory, and procedural memory pipelines |
| `specialized_agents/` | `CodeAgent`, `SqlAgent`, `ResearchAgent`, `DataAnalystAgent`, `BrowserAgent` |

---

## Types

The `types/` sub-package defines the data classes that flow between agent knots.

| Type | Description |
|------|-------------|
| `AgentMessage` | A single conversational turn: `role`, `content`, optional `name` and `metadata`. Frozen dataclass. |
| `AgentContext` | The full conversational state: an ordered tuple of `AgentMessage` plus a free-form `metadata` mapping. |
| `AgentResponse` | Outcome of one agent turn: `content`, tuple of `ToolCall`s, `finish_reason`, usage stats, raw metadata. |
| `ToolCall` | A single tool invocation requested by the LLM: `tool_name`, `arguments` mapping, optional `call_id`. |
| `ToolResult` | The result of executing a `ToolCall`: `call_id`, `tool_name`, `result` (any), optional `error`. |
| `Plan` | An ordered `tuple` of plan step strings plus an optional `rationale` string. |

---

## Building an agent pipeline

The example below wires a simple tool-using chat agent. Raw user text enters through a `Parameter`, flows through input parsing, context building, an LLM call, output parsing, a `SafetyCheck`, and a tool routing/execution pass before the formatted response exits.

**Scalar auto-coercion:** knot parameters typed `Knot | T` (e.g. `step: Knot | str`) accept either a parent knot or a plain scalar. When a scalar is passed, the framework automatically wraps it in a `Parameter` node so it participates in lineage and graph tracking — no manual wrapping required.

```python
import asyncio
from pirn import Tapestry, Parameter, KnotConfig, RunRequest
from pirn.domains.agents.input.message_parser import MessageParser
from pirn.domains.agents.input.context_builder import ContextBuilder
from pirn.domains.agents.generation.llm_call import LLMCall
from pirn.domains.agents.generation.output_parser import OutputParser
from pirn.domains.agents.generation.response_formatter import ResponseFormatter
from pirn.domains.agents.control.safety_check import SafetyCheck
from pirn.domains.agents.planning.planner import Planner
from pirn.domains.agents.planning.tool_router import ToolRouter
from pirn.domains.agents.planning.tool_executor import ToolExecutor

# Your provider and tool implementations.
from myapp.providers import AnthropicProvider
from myapp.tools import WebSearchTool

provider = AnthropicProvider(api_key="...", default_model="claude-sonnet-4-5")
search_tool = WebSearchTool(api_key="...")

async def main():
    with Tapestry() as t:
        raw = Parameter("user_input", str)

        messages = MessageParser(
            raw_input=raw,
            _config=KnotConfig(id="parse"),
        )
        context = ContextBuilder(
            messages=messages,
            system_prompt="You are a helpful research assistant.",
            _config=KnotConfig(id="context"),
        )
        raw_response = LLMCall(
            context=context,
            llm=provider,
            _config=KnotConfig(id="llm"),
        )
        safe = SafetyCheck(
            message=raw_response,
            deny_patterns=[r"\b(ignore previous instructions)\b"],
            _config=KnotConfig(id="safety"),
        )
        response = OutputParser(
            response=raw_response,
            _config=KnotConfig(id="parse_response"),
        )
        # Planner produces a Plan; extract first step for ToolRouter.
        plan = Planner(
            context=context,
            llm=provider,
            _config=KnotConfig(id="plan"),
        )
        route = ToolRouter(
            step=plan,
            tools=[search_tool],
            _config=KnotConfig(id="route_tools"),
        )
        tool_result = ToolExecutor(
            call=route,
            tools=[search_tool],
            _config=KnotConfig(id="exec_tools"),
        )
        output = ResponseFormatter(
            response=response,
            format="markdown",
            _config=KnotConfig(id="format"),
        )

    result = await t.run(
        RunRequest(parameters={"user_input": "What's the latest on quantum computing?"})
    )
    print(result.outputs["format"])
    await provider.close()

asyncio.run(main())
```

For higher-level patterns, use the pre-built `SubTapestry` pipelines from `specializations/`. For example, `NaiveRagPipeline` wraps the full retrieve-prompt-answer cycle in a single node:

```python
from pirn.domains.agents.specializations.rag.naive_rag_pipeline import NaiveRagPipeline

rag = NaiveRagPipeline(
    query=query_knot,
    memory_store=my_vector_store,
    llm=provider,
    top_k=5,
    _config=KnotConfig(id="rag"),
)
```

---

## Install

```bash
# Minimal — agents interfaces only, no heavy deps.
pip install pirn[agents]

# Add your chosen LLM provider's SDK separately:
pip install anthropic          # Anthropic
pip install openai             # OpenAI-compatible APIs

# If you need a vector store for memory:
pip install pinecone-client    # or qdrant-client, weaviate-client, etc.
```

The `agents` extra deliberately carries no mandatory heavy dependencies. LLM provider SDKs, vector databases, and tool libraries are installed separately so you pull only what your application uses.

**See also:** [Concepts](../getting-started/concepts.md), [Backends](../guides/backends.md)
