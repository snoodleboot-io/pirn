# Agentic Design Patterns in pirn

A practical guide to building single-agent and multi-agent systems using the
`pirn_agents` library. Each section names the pattern, maps it to the
concrete knots that implement it, and shows the minimal wiring code.

---

## Library Map

```
pirn_agents/
├── llm_provider.py          LLMProvider (interface — you supply a concrete impl)
├── tool.py                  Tool        (interface — you supply concrete tools)
├── memory_store.py          MemoryStore (interface — you supply a concrete impl)
├── types/
│   ├── agent_context.py     AgentContext
│   ├── agent_message.py     AgentMessage
│   ├── agent_response.py    AgentResponse
│   ├── plan.py              Plan
│   ├── tool_call.py         ToolCall
│   └── tool_result.py       ToolResult
├── input/
│   ├── context_builder.py   ContextBuilder   — assembles AgentContext from messages
│   ├── intent_classifier.py IntentClassifier — tags intent on a context
│   └── message_parser.py    MessageParser    — raw text → AgentMessage list
├── generation/
│   ├── llm_call.py          LLMCall          — calls LLMProvider.chat
│   ├── streaming_llm_call.py StreamingLLMCall
│   ├── output_parser.py     OutputParser     — raw response → AgentResponse
│   └── response_formatter.py ResponseFormatter
├── planning/
│   ├── planner.py           Planner          — context → Plan
│   ├── tool_router.py       ToolRouter       — step string → ToolCall list
│   ├── tool_executor.py     ToolExecutor     — executes one ToolCall
│   └── tool_result_aggregator.py ToolResultAggregator
├── memory/
│   ├── memory_retriever.py  MemoryRetriever  — MemoryStore.search
│   ├── memory_writer.py     MemoryWriter     — MemoryStore.store
│   └── conversation_buffer.py ConversationBuffer
├── control/
│   ├── handoff_check.py      HandoffCheck
│   ├── reflection_check.py   ReflectionCheck
│   ├── safety_check.py       SafetyCheck
│   └── termination_check.py  TerminationCheck
└── specializations/
    ├── react/               ReActLoop (SubTapestry)
    ├── rag/                 NaiveRagPipeline, CorrectiveRagPipeline, HyDeRagPipeline, GraphRagPipeline
    ├── multi_agent/         OrchestratorAgent, ParallelSpecialistFanOut, ConsensusAggregator, DebateFramework
    ├── memory_patterns/     SemanticMemoryPipeline, EpisodicMemoryPipeline, ProceduralMemoryPipeline, WorkingMemoryPipeline
    ├── guardrails/          InputGuardrailGate, OutputGuardrailGate, PiiRedactorCheck, FactCheckGate
    ├── structured_output/   JsonExtractorPipeline, YamlExtractorPipeline, PydanticValidatorPipeline, EnumClassifierPipeline
    ├── specialized_agents/  ReActLoop-based: BrowserAgent, CodeAgent, SqlAgent, ResearchAgent, DataAnalystAgent
    └── document_processing/ DocumentIngestionPipeline, DocumentQaPipeline, DocumentSummarizerPipeline, DocumentTranslationPipeline
```

### Concrete implementations

The three interfaces (`LLMProvider`, `Tool`, `MemoryStore`) have no production
concrete implementations in this library — they are deliberately left for your
application layer so pirn stays provider-agnostic. The test suite ships
`StubLLMProvider`, `StubMemoryStore`, and `StubTool` in
`tests/unit/domains/agents/conftest.py`; copy or adapt them for your own stubs
during development.

### `@tool` decorator

For plain functions, use `@tool` instead of subclassing `Tool`. Name, description,
and JSON Schema are derived from the function signature automatically.

```python
from pirn_agents import tool

@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return a summary of the top results."""
    ...

@tool
def lookup_policy(topic: str) -> str:
    """Look up an internal policy document by topic keyword."""
    return POLICIES.get(topic, "No policy found.")
```

The result is a `FunctionTool` (a `Tool` subclass). Pass it anywhere `Tool` is
accepted. Use `Tool` subclassing directly when the tool needs constructor-injected
dependencies (API keys, HTTP clients, connection pools).

### Scalar auto-coercion

Knot parameters typed `Knot | T` accept either a parent knot **or** a plain
scalar. When a scalar is passed the framework automatically wraps it in a
`Parameter` node — no manual wrapping required.

```python
# Both forms are equivalent:
router = ToolRouter(step=upstream_knot, tools=[...], _config=KnotConfig(id="r"))
router = ToolRouter(step="calculate compound interest", tools=[...], _config=KnotConfig(id="r"))
# In the second form the string becomes Parameter(default="calculate compound interest")
```

---

## Pattern 1 — Single Agent (Linear Chain)

**When to use:** One-shot Q&A, classification, summarisation — no loops or
branching required.

**Knots:** `MessageParser → ContextBuilder → LLMCall → OutputParser`

```python
from pirn.tapestry import Tapestry
from pirn.core.knot_config import KnotConfig
from pirn_agents.input.message_parser import MessageParser
from pirn_agents.input.context_builder import ContextBuilder
from pirn_agents.generation.llm_call import LLMCall
from pirn_agents.generation.output_parser import OutputParser

def build(llm, raw_text: str):
    t = Tapestry()
    parsed  = MessageParser(text=raw_text,   _config=KnotConfig(id="parse"))
    context = ContextBuilder(messages=parsed, _config=KnotConfig(id="ctx"))
    call    = LLMCall(context=context, llm=llm, _config=KnotConfig(id="call"))
    output  = OutputParser(response=call,    _config=KnotConfig(id="out"))
    t.store.register(parsed, context, call, output)
    return t
```

---

## Pattern 2 — ReAct Loop (Reason + Act)

**When to use:** Any task that may require tool use — the agent reasons, calls
tools, observes results, and repeats until it has a final answer.

**Knot:** `ReActLoop` (a `SubTapestry` — it owns its inner tapestry).

```python
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn.core.knot_config import KnotConfig

react = ReActLoop(
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    llm=my_llm,
    tools=[search_tool, calculator_tool],
    max_iterations=6,
    _config=KnotConfig(id="react"),
)
# Use inside a Tapestry or as a standalone SubTapestry
result: AgentResponse = await react.run()
```

The inner loop is an *unrolled* fixed-length chain — each step sits behind a
`ReActTerminationCheck` so early-exit steps short-circuit cheaply. `max_iterations`
sets the chain length.

---

## Pattern 3 — Planner / Tool-Router / Executor

**When to use:** Tasks where you want an explicit planning step — the agent
produces a `Plan` first, then routes each step to a tool, then aggregates results.

**Knots:** `ContextBuilder → Planner → ToolRouter → ToolExecutor* → ToolResultAggregator`

```python
from pirn_agents.planning.planner import Planner
from pirn_agents.planning.tool_router import ToolRouter
from pirn_agents.planning.tool_executor import ToolExecutor
from pirn_agents.planning.tool_result_aggregator import ToolResultAggregator

# One ToolExecutor per tool slot; ToolRouter writes ToolCall objects
# that each executor reads.
ctx      = ContextBuilder(messages=parsed, _config=KnotConfig(id="ctx"))
plan     = Planner(context=ctx, llm=llm,   _config=KnotConfig(id="plan"))
# Extract step string from plan, then route
step     = PlanFirstStep(plan=plan, _config=KnotConfig(id="step"))
router   = ToolRouter(step=step, tools=tools, llm=llm, _config=KnotConfig(id="route"))
executor = ToolExecutor(tool_call=router,  _config=KnotConfig(id="exec"))
agg      = ToolResultAggregator(results=executor, _config=KnotConfig(id="agg"))
```

---

## Pattern 4 — Generator + Critic (Refiner)

**When to use:** Writing, code generation, or any task where quality improves
through iterative self-critique. The generator produces a draft; the critic
scores it; the loop repeats until the `ReflectionCheck` is satisfied.

**Knots:** `LLMCall (generate) → ReflectionCheck → LLMCall (critique) → loop`

pirn implements this via the `ReflectionCheck` control knot. Wire two
`LLMCall` knots with a `ReflectionCheck` between them, then feed the critique
back into a dynamic DAG iteration:

```python
from pirn_agents.control.reflection_check import ReflectionCheck

draft    = LLMCall(context=ctx, llm=llm,            _config=KnotConfig(id="draft"))
gate     = ReflectionCheck(response=draft, threshold=0.8, _config=KnotConfig(id="gate"))
# gate outputs bool — use it to gate whether critique runs; pass the original ctx to LLMCall
critique = LLMCall(context=ctx, llm=critic_llm,    _config=KnotConfig(id="critique"))
# Wire gate's bool output into a Gate primitive or ErrorPolicy to conditionally run critique.
# Do NOT pass gate (bool) as context to LLMCall — LLMCall expects AgentContext.
```

For a dynamic loop (unknown number of iterations), use an extensible Tapestry
and have the critiquing knot register the next generator knot via
`get_current_store()` — identical to the `agent_loop` example pattern.

---

## Pattern 5 — Coordinator / Dispatcher

**When to use:** A top-level agent receives a task, classifies intent, and
routes it to the specialist best suited to handle it.

**Knot:** `OrchestratorAgent` (a `SubTapestry`).

```python
from pirn_agents.specializations.multi_agent.orchestrator_agent import (
    OrchestratorAgent,
)

orchestrator = OrchestratorAgent(
    task="Summarise the Q3 earnings report and flag risks.",
    llm=routing_llm,
    specialists={
        "summariser": SummarizerSubTapestry(...),
        "risk_analyst": RiskAnalystSubTapestry(...),
    },
    _config=KnotConfig(id="orchestrator"),
)
response: AgentResponse = await orchestrator.run()
```

`OrchestratorRouter` (inner knot) asks `routing_llm` to choose a specialist
by name; then that specialist's `process(task=task)` is called.

For a *dynamic* dispatcher that can change routing mid-run, implement a
custom `Knot` that calls `get_current_store().register(next_specialist)` —
see `examples/llm_agent/agent_loop.py` for this pattern.

---

## Pattern 6 — Parallel Fan-Out / Gather

**When to use:** The same task needs multiple independent perspectives
simultaneously (different LLMs, different retrieval strategies, domain
specialists). Results are gathered and either passed raw or synthesised.

**Knot:** `ParallelSpecialistFanOut` + optional `ConsensusAggregator`.

```python
from pirn_agents.specializations.multi_agent.parallel_specialist_fan_out import (
    ParallelSpecialistFanOut,
)
from pirn_agents.specializations.multi_agent.consensus_aggregator import (
    ConsensusAggregator,
)

fan_out = ParallelSpecialistFanOut(
    task="Assess this contract for legal and financial risk.",
    specialists={
        "legal":   LegalSpecialist(...),
        "finance": FinanceSpecialist(...),
    },
    _config=KnotConfig(id="fanout"),
)
# fan_out.run() returns {specialist_name: AgentResponse}

consensus = ConsensusAggregator(
    responses=fan_out,
    llm=synthesis_llm,
    strategy="llm_synthesis",   # or "majority_vote"
    _config=KnotConfig(id="consensus"),
)
```

For raw gather without synthesis, skip `ConsensusAggregator` and read the
mapping directly from `fan_out`.

---

## Pattern 7 — Synthesiser

**When to use:** Multiple upstream results (fan-out outputs, RAG chunks, tool
results) must be merged into a single coherent response.

**Knot:** `ConsensusAggregator` with `strategy="llm_synthesis"`, or
`ToolResultAggregator` for tool results, or a plain `LLMCall` whose
`ContextBuilder` receives a list of prior responses.

```python
# Simplest: feed all prior AgentResponses into a new ContextBuilder
ctx_synth = ContextBuilder(
    messages=[resp_a, resp_b, resp_c],
    _config=KnotConfig(id="ctx_synth"),
)
synthesis = LLMCall(context=ctx_synth, llm=llm, _config=KnotConfig(id="synth"))
```

---

## Pattern 8 — Hierarchical Decomposition

**When to use:** Complex goals that must be broken into sub-goals, each
handled by its own sub-agent — a tree of agents where each node can spawn
children.

pirn's `SubTapestry` is the natural unit: each node is a `SubTapestry` that
wires its own inner pipeline, and may itself instantiate child `SubTapestry`
nodes.

```python
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

class ResearchSubAgent(SubTapestry):
    def __init__(self, *, sub_task: str, llm, _config, **kw):
        super().__init__(sub_task=sub_task, llm=llm, _config=_config, **kw)

    async def _build_inner(self, inner: Tapestry, *, sub_task, llm, **_):
        react = ReActLoop(
            messages=[{"role": "user", "content": sub_task}],
            llm=llm, tools=[search_tool],
            max_iterations=4,
            _config=KnotConfig(id="inner_react"),
        )
        inner.store.register(react)
        return "inner_react"   # ID of the terminal knot

class TopLevelDecomposer(Knot):
    async def process(self, goal: str, llm, **_):
        sub_tasks = decompose(goal)   # your decomposition logic
        store = get_current_store()
        agents = [
            ResearchSubAgent(sub_task=t, llm=llm,
                             _config=KnotConfig(id=f"sub_{i}"))
            for i, t in enumerate(sub_tasks)
        ]
        for a in agents: store.register(a)
        # Wire a synthesiser over the agents' outputs
        ...
```

The `OrchestratorAgent` + nested `SubTapestry` specialists is the pre-built
version of this pattern for one level of decomposition.

---

## Pattern 9 — Blackboard (MAS Shared State)

**When to use:** Multiple specialised agents write partial results to shared
state; a coordinator reads from it when all contributions arrive.

pirn's knot graph *is* the blackboard: each knot's output is hashed and
stored in the run's lineage. To implement a classic blackboard:

1. Fan-out knots write to named slots (each knot is a "knowledge source").
2. An `Aggregator` (from `pirn.nodes.aggregator`) or a custom knot reads
   all slots by accepting them as kwargs.
3. A controller knot decides whether to trigger another round.

```python
from pirn.nodes.aggregator import Aggregator

# Slot writers (run in parallel — no dependencies between them)
syntax_check = SyntaxChecker(code=source, _config=KnotConfig(id="syntax"))
type_check   = TypeChecker(code=source,   _config=KnotConfig(id="types"))
security_scan = SecurityScanner(code=source, _config=KnotConfig(id="sec"))

# Blackboard reader
blackboard = Aggregator(
    combine=lambda **kw: kw,           # raw dict
    syntax=syntax_check,
    types=type_check,
    security=security_scan,
    _config=KnotConfig(id="blackboard"),
)

controller = ReviewController(board=blackboard, _config=KnotConfig(id="ctrl"))
```

---

## Pattern 10 — Supervision

**When to use:** An agent's output must pass safety or quality gates before
being returned to the caller.

**Knots:** `SafetyCheck`, `InputGuardrailGate`, `OutputGuardrailGate`,
`PiiRedactorCheck`, `FactCheckGate`.

Gates follow a common interface: they accept the upstream response and either
pass it through, redact it, or raise to abort the run.

```python
from pirn_agents.control.safety_check import SafetyCheck
from pirn_agents.specializations.guardrails.output_guardrail_gate import (
    OutputGuardrailGate,
)
from pirn_agents.specializations.guardrails.pii_redactor_gate import (
    PiiRedactorCheck,
)

raw_response = LLMCall(context=ctx, llm=llm, _config=KnotConfig(id="llm"))
safety       = SafetyCheck(response=raw_response, _config=KnotConfig(id="safety"))
pii          = PiiRedactorCheck(response=safety,  _config=KnotConfig(id="pii"))
output_gate  = OutputGuardrailGate(response=pii, llm=llm, _config=KnotConfig(id="oguard"))
```

Stack gates in order: safety first, then PII, then policy.

---

## Pattern 11 — Generator + Critic (Debate)

**When to use:** High-stakes decisions where you want adversarial pressure
between two or more agents debating a position before a judge decides.

**Knot:** `DebateFramework` (a `SubTapestry`).

```python
from pirn_agents.specializations.multi_agent.debate_framework import (
    DebateFramework,
)

debate = DebateFramework(
    topic="Should we refactor the auth module before the Q3 release?",
    debaters=[ProponentAgent(...), OpponentAgent(...)],
    judge_llm=judge_llm,
    rounds=3,
    _config=KnotConfig(id="debate"),
)
verdict: AgentResponse = await debate.run()
```

Each debater receives the topic plus a recap of all prior rounds; the judge
LLM picks the best position after all rounds complete.

---

## Pattern 12 — Memory Patterns

Four memory pipelines are available; each is a `SubTapestry`:

| Pipeline | Use when |
|---|---|
| `WorkingMemoryPipeline` | Keep a sliding window of recent context |
| `SemanticMemoryPipeline` | Fact store — store and retrieve factual assertions |
| `EpisodicMemoryPipeline` | Record interaction episodes for later recall |
| `ProceduralMemoryPipeline` | Remember how-to sequences (skills) |

```python
from pirn_agents.specializations.memory_patterns.semantic_memory_pipeline import (
    SemanticMemoryPipeline,
)

mem = SemanticMemoryPipeline(
    content="Paris is the capital of France.",
    llm=llm,
    memory_store=my_store,
    _config=KnotConfig(id="mem"),
)
await mem.run()   # stores extracted facts into my_store

from pirn_agents.memory.memory_retriever import MemoryRetriever

recall = MemoryRetriever(
    query="What is the capital of France?",
    memory_store=my_store,
    _config=KnotConfig(id="recall"),
)
```

---

## Pattern 13 — RAG Variants

Four retrieval-augmented generation pipelines:

| Pipeline | Best for |
|---|---|
| `NaiveRagPipeline` | Simple retrieval → prompt → answer |
| `CorrectiveRagPipeline` | Re-retrieves when relevance score is low |
| `HyDeRagPipeline` | Generates a hypothetical document first to improve recall |
| `GraphRagPipeline` | Graph-structured context (entities + relationships) |

```python
from pirn_agents.specializations.rag.corrective_rag_pipeline import (
    CorrectiveRagPipeline,
)

rag = CorrectiveRagPipeline(
    query="Explain the DICOM pixel data format.",
    llm=llm,
    memory_store=document_store,
    _config=KnotConfig(id="rag"),
)
answer: AgentResponse = await rag.run()
```

---

## Pattern 14 — Structured Output

Extract typed data from LLM responses:

```python
from pirn_agents.specializations.structured_output.pydantic_validator_pipeline import (
    PydanticValidatorPipeline,
)
from pirn_agents.specializations.structured_output.json_extractor_pipeline import (
    JsonExtractorPipeline,
)

# Extract and validate a Pydantic model from a raw LLM response
validated = PydanticValidatorPipeline(
    response=llm_call,
    schema=MySchema,
    llm=llm,         # used for retry/repair attempts
    _config=KnotConfig(id="validate"),
)
```

Also available: `YamlExtractorPipeline`, `EnumClassifierPipeline`.

---

## Pattern 15 — Specialised Agents

Pre-built `SubTapestry` agents backed by `ReActLoop`:

| Agent | What it does |
|---|---|
| `BrowserAgent` | Web search + scraping tasks |
| `CodeAgent` | Code generation + linting loop |
| `SqlAgent` | NL → SQL → execute → format |
| `ResearchAgent` | Multi-source research with citations |
| `DataAnalystAgent` | Statistical analysis with tool use |

All accept `task: str`, `llm: LLMProvider`, and a set of domain tools:

```python
from pirn_agents.specializations.specialized_agents.code_agent import (
    CodeAgent,
)

agent = CodeAgent(
    task="Write a Python function to parse ISO 8601 timestamps.",
    llm=llm,
    tools=[linter_tool],
    max_iterations=5,
    _config=KnotConfig(id="code_agent"),
)
code_response: AgentResponse = await agent.run()
```

---

## Pattern 16 — Agent as Tool

**When to use:** You want to expose an agent's capability as a `Tool` so that
another agent can call it as part of its ReAct loop — a handoff to a specialist,
or a "swarm" of agents each callable by name.

**Agent-as-tool is first-class** (F7): any `SubTapestry` agent that mixes in
`AgentAsToolMixin` (the shipped specialist agents do) becomes a `Tool` in one
call via `agent.as_tool()`, or wrap any agent with the `as_tool(agent)` free
function. No hand-written adapter, no manual schema:

- `name`/`description` default from the agent and are overridable.
- `parameters_schema` is derived from the agent's `process` inputs (falling back
  to `{task: str}`).
- `invoke()` runs the inner agent and maps its `AgentResponse` into the F1
  `ToolResult` shape (structured passthrough — `content`, `tool_calls`, `usage`,
  `cost` — not just `.content`); an inner failure surfaces as a tool error.

Safety and performance come built in and are shared with the handoff/swarm path
(both funnel through the same `invoke_agent` machinery): a **max nesting depth**
plus **cycle detection** reject a self-referential graph before it recurses
forever; the parent's **budget/deadline/token** limits are *inherited* by nested
agents (a nested loop can't outrun the caller); and the parent's **pooled
`LLMProvider`** is reused by identity rather than reconstructed per call.

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents import as_tool  # or: agent.as_tool()
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.specializations.specialized_agents.research_agent import (
    ResearchAgent,
)
from pirn_agents.types.agent_message import AgentMessage

with Tapestry() as tapestry:
    researcher = ResearchAgent(
        topic="seed",
        llm=llm,
        search_tool=search_tool,
        max_searches=3,
        _config=KnotConfig(id="researcher"),
    )
    # One line: the agent is now a Tool. Nested runs reuse `llm` (by identity)
    # and inherit the budget; a self-call is rejected before it recurses.
    research_tool = researcher.as_tool(
        name="research",
        provider=llm,
        budget=RunBudget(max_iterations=8, deadline_seconds=30.0),
    )

    ReActLoop(
        messages=(AgentMessage(role="user", content="Research CRISPR advances."),),
        llm=llm,
        tools=(research_tool,),
        max_iterations=3,
        _config=KnotConfig(id="outer"),
    )

result = await tapestry.run(RunRequest())
```

Equivalently, `as_tool(researcher, name="research")` returns the same
`AgentTool`. A swarm is just a `ReActLoop` whose `tools` are several
`agent.as_tool()` wrappers — the loop hands off to whichever the planner names.

---

## Pattern 17 — MCP (Model Context Protocol) Usage

**When to use:** You need to connect to an external MCP server — a remote tool
provider exposing resources, prompts, and tools via the standard protocol.

The `pirn_agents.mcp` subpackage (behind the `[mcp]` extra) ships a first-class
async client and adapters, so you no longer hand-roll an `McpTool`. The design is
a **thin JSON-RPC core** (`McpClient`) driving a pluggable **transport**
(`StdioTransport`, `StreamableHttpTransport`, or your own `McpTransport`); the
`mcp` SDK is imported lazily and used only for real transport plumbing, so
`import pirn_agents` stays backend-free. Adapters map the server's surface onto
F1 primitives:

* `McpTool` / `McpToolset` → an F1 `Toolset` (discovery);
* `McpResourceAdapter` → context injection (`ContextBuilder` / `MemoryStore`);
* `McpPromptAdapter` / `McpPromptTemplate` → reusable message templates;
* `McpConnector` / `McpSessionPool` → one long-lived session per server, vended
  through F2's `ToolClientKnot`, with reconnect + jittered backoff.

```python
from pirn.core.knot_config import KnotConfig
from pirn_agents.mcp import McpConnector, McpToolset, StdioTransport

# One pooled, self-healing session per server (built once, reused for the run).
connector = McpConnector(
    transport_factory=lambda: StdioTransport(command="python", args=["-m", "my_server"]),
)
session = await connector.session()          # opens transport + initialize handshake

# Discover the server's tools as a native Toolset and wire into any knot.
toolset = await McpToolset(client=session).discover()

react = ReActLoop(
    messages=[{"role": "user", "content": task}],
    llm=llm,
    tools=list(toolset),                     # each entry is an McpTool(Tool)
    max_iterations=8,
    _config=KnotConfig(id="mcp_react"),
)
```

Schemas and results **round-trip through F1's protocol**: `toolset.schema()` is
the provider-neutral tool schema, and a `ToolCall` dispatched through
`ParallelToolExecutor` invokes `McpTool.invoke` → `tools/call` and wraps the
result into a `ToolResult` (a server `isError` becomes `ToolStatus.ERROR`). For
executor-free use, `McpTool.as_tool_result(call)` returns the `ToolResult`
directly.

**Resources** map to context injection: `McpResourceAdapter(client=session)`
lists/reads resources and yields either system-role `AgentMessage`s
(`as_context_messages()`, prepend at `ContextBuilder` time) or writes them into a
`MemoryStore` (`inject_into_store(store)`) for a `MemoryRetriever`.

**Prompts** map to reusable templates: `McpPromptAdapter(client=session)
.build_template(name)` captures a prompt once, and `template.render({...})`
substitutes arguments (validated via `isinstance`) into a list of `AgentMessage`s
without another round-trip.

For several servers, register per-server connector factories on an
`McpSessionPool` and call `await pool.session(key)` — each key's session is
constructed once and reused.

---

## Pattern 18 — Swarm (Decentralised Multi-Agent)

**When to use:** No central coordinator — agents hand off to one another
dynamically based on task state, similar to OpenAI Swarm.

Use pirn's extensible Tapestry: each agent knot decides at runtime which
agent to register as the next node.

```python
from pirn.tapestry import get_current_store
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

class TriageAgent(Knot):
    async def process(self, message: str, llm, tools, **_):
        intent = classify_intent(message)   # lightweight local check
        store = get_current_store()
        if intent == "code":
            store.register(CodeAgent(task=message, llm=llm, tools=tools,
                                     _config=KnotConfig(id="code")))
        elif intent == "research":
            store.register(ResearchAgent(task=message, llm=llm, tools=tools,
                                         _config=KnotConfig(id="research")))
        else:
            store.register(GeneralistAgent(task=message, llm=llm, tools=tools,
                                           _config=KnotConfig(id="general")))
        return message   # pass-through; next agent reads it

t = Tapestry()
t.store.register(TriageAgent(message=user_input, llm=llm, tools=tools,
                             _config=KnotConfig(id="triage")))
result = await t.run(extensible=True)
```

Each agent can similarly hand off to another, creating a dynamic chain without
a central controller.

---

# Agentic Design Patterns — F8 expansion (PIR-21)

Patterns 19–27 add the standard agentic shapes not covered above. Each is a
provider-neutral `SubTapestry` reusing F1 (parallel executor), F4 (memory),
F7 (agents-as-tools), and F10 (run budgets). See
`specializations/PATTERNS_TAXONOMY_F8.md` for the net-new/compositional
classification and citations.

## Pattern 19 — ReWOO (Reasoning WithOut Observation)

Plan every tool call up front, execute them in parallel through the F1 executor,
then synthesise once — a fixed **two** LLM round-trips regardless of tool count,
versus one-per-step for ReAct. Knots: `ReWooPlanner` → `ParallelToolExecutor`
(F1) → `ReWooSynthesizer`, wired by `ReWooPipeline` into a `ReWooResult`.

```python
from pirn_agents.specializations.rewoo.rewoo_pipeline import ReWooPipeline

with Tapestry() as t:
    ReWooPipeline(
        goal="Compare the populations of France and Spain.",
        llm=my_provider,
        tools=(population_tool,),      # each a Tool
        max_concurrency=8,
        _config=KnotConfig(id="rewoo"),
    )
result = (await t.run(RunRequest())).outputs["rewoo"]   # ReWooResult(answer, plan, results)
```

## Pattern 20 — Reflexion (actor / evaluator / self-reflection + memory)

Actor drafts, evaluator scores, reflector writes a verbal lesson to F4 memory that
is **read back** on the next attempt; bounded by `max_iterations`. Knots:
`ReflexionActor`, `ReflexionEvaluator`, `ReflexionReflector`, orchestrated by
`ReflexionPipeline` into a `ReflexionResult`.

```python
from pirn_agents.specializations.reflexion.reflexion_pipeline import ReflexionPipeline

with Tapestry() as t:
    ReflexionPipeline(
        task="Write a correct binary-search implementation.",
        llm=my_provider,
        memory=my_memory_store,        # a MemoryStore (F4)
        max_iterations=3,
        _config=KnotConfig(id="rx"),
    )
result = (await t.run(RunRequest())).outputs["rx"]   # ReflexionResult(answer, succeeded, attempts)
```

## Pattern 21 — Evaluator-Optimizer (LLM-as-judge accept loop)

Generator produces a candidate, an `LlmJudge` returns a numeric `JudgeVerdict`, and
`AcceptGate` — the scored generalisation of `control.reflection_check.ReflectionCheck`
— stops on threshold. An optional `ReflectionCheck` can be injected as an early-stop
gate (reuse, not duplication).

```python
from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_pipeline import (
    EvaluatorOptimizerPipeline,
)

with Tapestry() as t:
    EvaluatorOptimizerPipeline(
        task="Draft a crisp product tagline.",
        llm=my_provider,
        threshold=8.0,                 # 0-10 judge scale
        max_iterations=3,
        _config=KnotConfig(id="eo"),
    )
result = (await t.run(RunRequest())).outputs["eo"]   # EvaluatorOptimizerResult(answer, score, accepted)
```

## Pattern 22 — Router + typed Fallback chain

`CandidateRouter` orders typed `RouteCandidate`s best-first by confidence; `FallbackChain`
invokes them in order, skipping sub-threshold candidates and stopping on first success —
avoiding the wasted retries of a naive "try everything" baseline. Wired by
`RouterFallbackPipeline` into a `FallbackResult`.

```python
from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.specializations.routing.router_fallback_pipeline import RouterFallbackPipeline

candidates = (
    RouteCandidate(name="fast", tool=fast_tool, min_confidence=0.6),
    RouteCandidate(name="strong", tool=strong_tool),
)
with Tapestry() as t:
    RouterFallbackPipeline(
        candidates=candidates,
        confidences={"fast": 0.9, "strong": 0.4},   # from an intent router / heuristic
        arguments={"input": "the query"},
        _config=KnotConfig(id="rf"),
    )
result = (await t.run(RunRequest())).outputs["rf"]   # FallbackResult(succeeded, chosen, attempted, skipped)
```

## Pattern 23 — Orchestrator-Workers (dynamic, via F7)

`OrchestratorWorkers` spawns one worker (an F7 `AgentTool`) per task-list item, bounded by
a max-concurrency semaphore, and aggregates an `OrchestratorWorkersResult`. Worker count
scales with the task list; wall-clock stays bounded by the cap.

```python
from pirn_agents.agent_tool import AgentTool
from pirn_agents.specializations.multi_agent.orchestrator_workers import OrchestratorWorkers

worker = AgentTool(my_specialist_agent)      # F7 agent-as-tool
with Tapestry() as t:
    OrchestratorWorkers(
        tasks=("summarise doc A", "summarise doc B", "summarise doc C"),
        worker=worker,
        max_concurrency=4,
        _config=KnotConfig(id="ow"),
    )
result = (await t.run(RunRequest())).outputs["ow"]   # OrchestratorWorkersResult(results, succeeded, total)
```

## Pattern 24 — LATS / tree-search act (budgeted)

`LatsSearch` runs a best-first (MCTS-style) search over action trajectories proposed by
`LatsActionProposer` and scored by a pluggable `TrajectoryValueModel`, **strictly bounded**
by an F10 `RunBudget` (node count and/or wall-clock). Returns a `LatsResult`.

```python
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.specializations.lats.lats_search import LatsSearch

with Tapestry() as t:
    LatsSearch(
        task="Plan a route through the maze.",
        llm=my_provider,
        value_model=my_value_model,           # a TrajectoryValueModel (stubbable)
        budget=RunBudget(max_iterations=64, deadline_seconds=5.0),
        max_depth=4,
        _config=KnotConfig(id="lats"),
    )
result = (await t.run(RunRequest())).outputs["lats"]   # LatsResult(best_trajectory, best_value, nodes_expanded)
```

## Pattern 25 — Self-Ask

`SelfAskPipeline` decomposes a question into follow-up sub-questions, answers each, then
composes the final answer into a `SelfAskResult`.

```python
from pirn_agents.specializations.self_ask.self_ask_pipeline import SelfAskPipeline

with Tapestry() as t:
    SelfAskPipeline(task="Who directed the highest-grossing film of 1997?", llm=my_provider,
                    _config=KnotConfig(id="sa"))
result = (await t.run(RunRequest())).outputs["sa"]   # SelfAskResult(final_answer, subquestions, subanswers)
```

## Pattern 26 — Plan-ReAct

`PlanReActPipeline` plans first with `TaskPlanner`, then runs a `ReActLoop` per step — pure
composition of existing knots — into a `PlanReActResult`.

```python
from pirn_agents.specializations.plan_react.plan_react_pipeline import PlanReActPipeline

with Tapestry() as t:
    PlanReActPipeline(task="Research and summarise X.", llm=my_provider, tools=(search_tool,),
                      max_iterations=4, max_steps=5, _config=KnotConfig(id="pr"))
result = (await t.run(RunRequest())).outputs["pr"]   # PlanReActResult(plan, step_responses, final)
```

## Pattern 27 — Prompt-chaining

`PromptChainPipeline` runs a fixed sequence of LLM calls where each output feeds the next,
into a `PromptChainResult`.

```python
from pirn_agents.specializations.prompt_chaining.prompt_chain_pipeline import PromptChainPipeline

with Tapestry() as t:
    PromptChainPipeline(task=long_document, llm=my_provider,
                        steps=("Summarise in 3 bullets.", "Translate the summary to French."),
                        _config=KnotConfig(id="pc"))
result = (await t.run(RunRequest())).outputs["pc"]   # PromptChainResult(outputs, final)
```

---

## Composing Patterns

Patterns compose — pick the pieces you need:

```
[InputGuardrailGate]                       ← supervision
   → [IntentClassifier]                    ← routing input
   → [OrchestratorAgent]                   ← coordinator/dispatcher
       ├── [ReActLoop + SearchTool]         ← react (research leg)
       ├── [CorrectiveRagPipeline]          ← RAG (document leg)
       └── [CodeAgent]                      ← specialised agent (code leg)
   → [ConsensusAggregator]                  ← synthesiser
   → [PiiRedactorCheck → OutputGuardrailGate] ← supervision (output)
```

All of the above are real knots in this library. The only things you supply
are concrete `LLMProvider`, `Tool`, and `MemoryStore` implementations.

---

## Choosing Between SubTapestry and Dynamic DAG

| Approach | When to use |
|---|---|
| `SubTapestry` | Fixed structure; inner graph known at build time |
| Dynamic DAG (`extensible=True`) | Unknown iteration count; agents spawn agents |
| Pre-built `SubTapestry` specialisations | Standard patterns — reach for these first |

The pre-built specialisations (`ReActLoop`, `OrchestratorAgent`, etc.) are
`SubTapestry` instances with fixed inner graphs. The `examples/llm_agent/`
directory shows the dynamic DAG approach for cases where the pipeline shape
is not known ahead of time.

---

## Tool-call protocol & ParallelToolExecutor

pirn's tool-calling vocabulary is provider-neutral: three small types plus a
registry, with no LLM provider baked in.

| Type | Role |
|---|---|
| `ToolCall` | One decided invocation: `tool_name`, `arguments`, `call_id`, optional `raw`. |
| `ToolResult` | Its outcome: `call_id`, `result`, `error`, `status`, `latency`, `tokens`. |
| `ToolStatus` | Terminal disposition — `OK`, `ERROR`, `TIMEOUT`, `CANCELLED`. |
| `Toolset` | Immutable, ordered, unique-by-name registry of `Tool`s. |

`ParallelToolExecutor` runs a batch of `ToolCall`s concurrently against a
`Toolset` with **bounded concurrency**, a **per-call timeout**, jittered-backoff
**retries**, and **failure isolation** — one slow, raising, or timing-out call
never aborts its siblings. Results come back in input order, each carrying its
own `status` and `latency`.

```python
import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_call import ToolCall
from pirn_agents.types.tool_status import ToolStatus


class StubTool(Tool):
    """A provider-neutral tool; a real tool would call an API, DB, etc."""

    def __init__(self, *, name: str, reply: str) -> None:
        self._name = name
        self._reply = reply

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"echoes for {self._name}"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {"q": {"type": "string"}}}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return f"{self._reply}:{arguments.get('q', '')}"


toolset = Toolset([StubTool(name="search", reply="hit"),
                   StubTool(name="lookup", reply="doc")])
calls = [
    ToolCall(tool_name="search", arguments={"q": "dicom"}, call_id="c1"),
    ToolCall(tool_name="lookup", arguments={"q": "policy"}, call_id="c2"),
]

with Tapestry():
    executor = ParallelToolExecutor(
        tool_calls=[], toolset=Toolset(),
        _config=KnotConfig(id="pte", validate_io=False),
    )

results = await executor.process(
    tool_calls=calls, toolset=toolset,
    max_concurrency=8, timeout=5.0, retries=1,
)
for r in results:
    assert r.status is ToolStatus.OK
    print(r.call_id, r.result, f"{r.latency:.4f}s")
```

Construction-time knobs `retry_base` / `retry_jitter` tune the backoff *shape*;
`hook` (below) wires observability. All three are constructor kwargs rather than
`process` parameters because they configure *how* the executor runs, not *what*
it executes.

---

## Native tool-calling via ToolCallCodec

`ToolCallCodec` maps pirn's neutral tool-calling types to and from any provider's native JSON. The codec itself is provider-agnostic; all provider shaping lives behind a `ProviderAdapter` you implement once per provider. Swapping providers means swapping adapters — the codec never changes.

```python
from __future__ import annotations
from typing import Any
from pirn_agents.provider_adapter import ProviderAdapter
from pirn_agents.tool_call_codec import ToolCallCodec
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_result import ToolResult

class MyAdapter(ProviderAdapter):
    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        return {"type": "function", "function": neutral_tool}
    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        return list(provider_msg["tool_calls"])  # each: {"id","name","arguments"}
    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        return {"role": "tool", "tool_call_id": result_payload["call_id"], "content": result_payload["content"]}

codec = ToolCallCodec(MyAdapter())
native_tools = codec.encode_tools(toolset)      # declare tools to the provider
calls = codec.decode_calls(assistant_msg)       # -> list[ToolCall] (single or parallel; args JSON-str or dict)
tool_msgs = codec.encode_results(results)       # -> native tool-result messages
```

---

## Streaming tool-call parsing

`StreamingToolCallParser` assembles a provider's streamed argument fragments
into `ToolCall`s and emits each one *the instant* its index is complete —
before the stream finishes — so the executor can start dispatching while later
calls are still arriving. It consumes a **neutral delta shape**
(`index`, `id`, `name`, `arguments` fragment, optional `done`); translating a
provider's native streaming events into that shape is an adapter's job, exactly
as with `ToolCallCodec`. A tail that never parses as valid JSON is dropped
(counted in `parser.dropped_partial`) rather than raising.

```python
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn_agents.streaming_tool_call_parser import StreamingToolCallParser


async def provider_deltas() -> AsyncIterator[Mapping[str, Any]]:
    # Neutral deltas an adapter would produce from a native stream.
    yield {"index": 0, "id": "c1", "name": "search", "arguments": '{"q":"di'}
    yield {"index": 0, "arguments": 'com"}', "done": True}
    yield {"index": 1, "id": "c2", "name": "lookup", "arguments": '{"q":"policy"}', "done": True}


parser = StreamingToolCallParser()

# Drain eagerly (each call is available as soon as it completes)...
calls = [call async for call in parser.parse(provider_deltas())]
# ...or collect them in one shot:
calls = await parser.parse_to_list(provider_deltas())

results = await executor.process(
    tool_calls=calls, toolset=toolset,
    max_concurrency=8, timeout=5.0, retries=0,
)
assert parser.dropped_partial == 0
```

---

## Observability hooks

`ToolInvocationHook` is the seam for observing every tool invocation the
executor runs — `on_start` just before a tool is invoked and `on_finish` once
its `ToolResult` is built (for *every* outcome: ok, error, timeout, not-found).
`on_start` carries a short, stable `args_digest` (a SHA-256 prefix over the
call's arguments) so you can correlate without recording raw argument values;
`on_finish` carries the terminal `ToolStatus` and per-call `latency`.

The base class is a genuine **no-op by design**, not a stub: an executor given
no hook (or the base hook) does zero observability work — the digest is not even
computed — so the property is **zero-cost when absent**. Subclass it to emit
spans or metrics (this feeds the metrics and tracing surfaces). Hook exceptions
are swallowed and logged by the executor, so a misbehaving hook can never abort
or alter tool execution.

```python
import time

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.parallel_tool_executor import ParallelToolExecutor
from pirn_agents.tool_invocation_hook import ToolInvocationHook
from pirn_agents.toolset import Toolset
from pirn_agents.types.tool_status import ToolStatus


class MetricsHook(ToolInvocationHook):
    """Emit a counter per invocation and a latency histogram per outcome."""

    def __init__(self, metrics) -> None:  # your provider-neutral metrics sink
        self._metrics = metrics
        self._spans: dict[str, float] = {}

    def on_start(self, *, tool_name: str, args_digest: str, call_id: str) -> None:
        self._metrics.increment("tool.calls", tags={"tool": tool_name})
        self._spans[call_id] = time.perf_counter()

    def on_finish(self, *, tool_name: str, call_id: str,
                  status: ToolStatus, latency: float) -> None:
        self._metrics.observe(
            "tool.latency", latency,
            tags={"tool": tool_name, "status": status.value},
        )
        self._spans.pop(call_id, None)


with Tapestry():
    executor = ParallelToolExecutor(
        tool_calls=[], toolset=Toolset(),
        hook=MetricsHook(my_metrics),          # omit → zero-cost no-op default
        _config=KnotConfig(id="pte", validate_io=False),
    )
```

Leave `hook` unset (or pass the base `ToolInvocationHook()`) for the inert
default; the result path is byte-for-byte identical either way.

---

## Performance, observability & benchmark harness (F10)

F10 provides the cross-cutting perf levers (budgets, caching, concurrency) and
the measurement harness the rest of the project is held to. Everything here is
pure-python and provider-neutral; the one optional backend (OTel) is lazily
imported behind the `otel` extra.

### RunBudget — iteration / token / deadline caps + cooperative cancellation

`RunBudget` is a frozen value holding the *limits*; `RunBudgetMeter` is the
mutable accountant threaded through a loop that spends against them. On the
first breach the meter cancels a shared `CancellationToken` **and** raises the
typed `BudgetBreachError`, so the loop unwinds cleanly (no partial state) and
can return a typed terminal result rather than leaking an exception.

```python
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.performance.budget_breach_error import BudgetBreachError

meter = RunBudgetMeter(RunBudget(max_iterations=6, max_tokens=8000, deadline_seconds=30.0))

async def agent_loop(meter: RunBudgetMeter) -> str:
    while True:
        try:
            meter.spend_iteration()          # raises BudgetBreachError past the cap
        except BudgetBreachError as exc:
            return f"stopped: {exc.limit.value}"   # clean, typed terminal result
        reply = await call_llm(...)
        meter.spend_tokens(reply.token_count)
        # A shared token lets in-flight tool legs cancel cooperatively:
        # pass `meter.token` to leg coroutines and have them call
        # `token.raise_if_cancelled()` at their own checkpoints.
```

This is the single shared enforcement path an F7/F8/F9 loop consumes: each loop
accepts an optional `RunBudgetMeter` (or builds one from a `RunBudget`) and
calls the same `spend_*` / `checkpoint` methods, so budget semantics never
diverge between patterns.

### ConcurrencyConfig + BackpressureSemaphore — shared bounded concurrency

`ConcurrencyConfig` is the one knob object (max concurrency, optional queue
depth, acquire timeout) executors and provider call sites consume instead of
hard-coding an `asyncio.Semaphore(8)`. `BackpressureSemaphore` turns it into a
limiter whose `slot()` context manager queues by default (never fails) and
sheds load with a typed `asyncio.QueueFull` only when an explicit
`max_queue_depth` is set. `ParallelToolExecutor`'s internal
`asyncio.Semaphore(max_concurrency)` is exactly `ConcurrencyConfig.max_concurrency`
— a wiring would replace that line with `BackpressureSemaphore(config).slot()`
around each dispatch, no other change.

```python
from pirn_agents.performance.concurrency_config import ConcurrencyConfig
from pirn_agents.performance.backpressure_semaphore import BackpressureSemaphore

limiter = BackpressureSemaphore(ConcurrencyConfig(max_concurrency=4, max_queue_depth=32))
async with limiter.slot():        # queues under load; QueueFull past the depth bound
    await call_provider(...)
```

### Caching — content-addressed result cache + semantic + prompt-cache passthrough

`ResultCache.get_or_compute(payload, compute)` memoises idempotent tool calls
and embedding lookups keyed off a `content_address` of the inputs (mirrors the
DAG's content addressing). `SemanticResultCache.get_or_compute_semantic(text,
compute)` matches on embedding similarity using a caller-injected embedding fn
(no backend). `PromptCachePassthrough` defers to a provider's native prompt
cache when it exposes one, else signals the caller to cache locally.

```python
from pirn_agents.caching.in_memory_result_cache import InMemoryResultCache

cache = InMemoryResultCache(max_entries=1024)
result = await cache.get_or_compute({"tool": "search", "args": {"q": "dicom"}}, run_search)
```

### Observability — span/callback interface + pluggable sink (generalises F1)

`Tracer` opens `Span`s around LLM, tool, and retrieval calls and reports them to
a pluggable `ObservabilitySink` that is a genuine no-op by default (zero
required backend), exactly like F1's `ToolInvocationHook`. F1's tool hook
re-enters this interface via `SpanEmittingToolInvocationHook`, so tool spans
land in the same sink as LLM/retrieval spans without duplicate instrumentation.
Concrete sinks: `LoggingSink` (stdlib logging) and `OtelSink` (behind the lazy
`otel` extra).

```python
from pirn_agents.observability.tracer import Tracer
from pirn_agents.observability.span_emitting_tool_invocation_hook import (
    SpanEmittingToolInvocationHook,
)

tracer = Tracer(LoggingSink())                     # or Tracer() for the no-op default
async with tracer.llm_span(name="llm.chat") as span:
    span.set_attribute("model", "…")
    ...
# same tracer/sink for tool spans, via the F1 hook seam:
executor = ParallelToolExecutor(..., hook=SpanEmittingToolInvocationHook(tracer))
```

### Benchmark harness — `[benchmark]` lines → report → delta

`@pytest.mark.benchmark` cases measure with `time.perf_counter` (no
pytest-benchmark plugin) and print `[benchmark] <name> k=v …` lines — the format
F1/F2 micro-benchmarks already emit. `BenchmarkReport.from_output(text)` parses
a run into a JSON document; `BenchmarkDelta(baseline, current)` diffs it against
a stored baseline and renders `to_json()` (machine-readable) or `to_markdown()`
(a PR comment), so perf deltas are captured consistently across features.

```python
from pirn_agents.benchmarks.benchmark_report import BenchmarkReport
from pirn_agents.benchmarks.benchmark_delta import BenchmarkDelta

current = BenchmarkReport.from_output(captured_pytest_output)
baseline = BenchmarkReport.from_json(open("baseline.json").read())
print(BenchmarkDelta(baseline, current).to_markdown())
```
