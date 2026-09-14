# Base Tool Library (PAE-F6)

A curated set of production-grade tools agents can use out of the box — the
"batteries" for the batteries-included runtime. Since the ADR "agents speaks
core" (WS1) **a tool is a `Knot` class**: `Tool(Knot)` declares its call
arguments on `process()`, derives its provider-neutral JSON schema from that
signature (`Tool.declaration()` → `input_json_schema()`), and one call is one
tool knot the engine runs — with its own `Ok | Err | Skipped`, lineage row,
timeout, retry and concurrency group. Optional backends (`httpx`, `aiosqlite`)
are imported lazily at call time, so `import pirn_agents` stays backend-free.

## The shape of a tool

```python
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.tool import Tool


class RetrieverTool(Tool):
    """Retrieve the most relevant stored records for a query, ranked by similarity."""

    tool_name: ClassVar[str] = "retriever"          # default: snake_case of the class name

    def __init__(self, *, query: Knot | str, store: Knot | MemoryStore,
                 top_k: Knot | int = 5, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(query=query, store=store, top_k=top_k, _config=_config, **kwargs)

    async def process(
        self,
        query: Annotated[str, Field(description="The retrieval query.")],
        store: MemoryStore,                          # a collaborator, bound once
        top_k: Annotated[int, Field(description="Number of results.")] = 5,
        **_: Any,
    ) -> Mapping[str, Any]:
        ...
```

* The description shown to the model is the class docstring's first paragraph;
  argument descriptions come from `Annotated[..., Field(description=...)]`.
* Collaborators (stores, clients, providers) are ordinary inputs that are
  **bound once** into a capability: `RetrieverTool.bind(store=my_store)`.
  Bound inputs are hidden from the declaration; `.defaults(top_k=3)` keeps an
  input callable but shows the default; `.named("search_notes", description=...)`
  renames the capability.
* `Tool.bind(...)` / `Tool.factory()` return a `ToolFactory` — the *capability*
  value a `Toolset` holds (a `KnotFactory` + declaration + facets:
  `permissions`, `requires_approval()`, `streaming`, `stateful`).
  `ToolFactory.for_call(call)` constructs the tool knot for one `ToolCall`
  inside the current tapestry; `ToolFactory.run_call(call)` runs one call in
  a throwaway tapestry and returns its `Result`.
* `@ToolDecorator.decorate` on a function is `@knot` plus a declaration; `McpTool` is
  `KnotFactory.from_schema` over the remote tool's schema; an agent is a tool
  through `AgentTool` (`agent.as_tool()`), whose nesting guard is core's
  `RunNesting`.

## Tool catalog

| Tool | Class | Backend / extra | Notes |
|------|-------|-----------------|-------|
| `calculator` | `CalculatorTool` | none (stdlib) | AST-based safe arithmetic; no `eval`/`exec` |
| `read_file` / `write_file` / `list_dir` / `glob` | `ReadFileTool` … | none (stdlib) | root-scoped, traversal + symlink guarded |
| `web_search` | `WebSearchTool` | injected `SearchBackend` | vendor-neutral search |
| `http_request` | `HttpRequestTool` | `web` (`httpx`) | SSRF guard, host allowlist, size cap |
| `html_to_text` | `HtmlToTextTool` | none (stdlib) | strips scripts/styles, output cap |
| `sql_query` | `SqlQueryTool` | injected `SqlConnector` | read-only guard + row cap |
| `python_exec` / `shell` | `PythonExecTool` / `ShellTool` | injected `SandboxExecutor` | **opt-in, off by default** |
| `retriever` | `RetrieverTool` | injected `MemoryStore` (F4) | ranked retrieval |
| `rag` | `RagTool` | `MemoryStore` + `LLMProvider` | RAG-as-a-tool |
| `McpTool` | re-exported (F5) | `mcp` | remote MCP tool as a first-class base tool |

## Toolset bundles

Factory functions in `pirn_agents.tools.bundles` group related tools with sane
defaults. They only *bind* capabilities, so importing them triggers no backend
imports:

```python
from pirn_agents.tools.bundles import Bundles

tools = Bundles.calculator_toolset() + Bundles.web_toolset() + Bundles.filesystem_toolset(root="/srv/workspace")
```

`Toolset` maps a name to a `ToolFactory` (a `Tool` class, a bound factory, a
`@ToolDecorator.decorate` function or a legacy instance are all normalised through
`ToolFactory.of`). It supports `+` / `merge` (unique names re-checked),
`get(name)`, iteration, and `schema()` (provider-neutral declaration list).

## Registering a Toolset with a ReActLoop

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.tools.bundles import Bundles
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.messaging.agent_message import AgentMessage

toolset = Bundles.calculator_toolset() + Bundles.retrieval_toolset(store=my_store)

with Tapestry() as tapestry:
    ReActLoop(
        messages=(AgentMessage(role="user", content="What is 21 * 2?"),),
        llm=my_llm_provider,          # any LLMProvider — provider-neutral
        tools=tuple(toolset),
        max_iterations=6,
        _config=KnotConfig(id="loop"),
    )
run = await tapestry.run(RunRequest())
response = run.outputs["loop"]        # AgentResponse
```

Under F1 schema-based tool calling, a batch of `ToolCall`s is dispatched through
`ParallelToolExecutor` — a `SubTapestry` that constructs one tool knot per call
under the `"tools"` concurrency group, with per-knot `timeout` and
`retry=KnotRetryPolicy(...)` — and `ToolCallCodec` turns the run's `Result`s
back into the model's tool-result messages. A single call is a `ToolInvocation`
knot. The text ReAct loop supplies each action input as `{"input": ...}`;
single-argument base tools accept that as an alias for their canonical
parameter, so the same tool works both ways. `ToolResult` is the model-facing
*view* of a call's `Result` — its `outcome` is that `Result`, and its `status`
is a string derived from it (`"ok"`, `"error"`, `"timeout"`, `"skipped"`) —
built by `ToolResult.from_result(call_id, result, lineage)`.

## Security notes

### Human approval (`ToolPermissions.approval_required`)

A capability whose `permissions = ToolPermissions(approval_required=True)`
needs a human (or a policy engine) to approve each call before it runs:

```python
from pirn_agents.agent.approval_hook import ApprovalHook

class SlackPrompt(ApprovalHook):
    async def request_approval(self, *, tool_name: str, arguments: Mapping[str, Any]) -> bool:
        return await ask_a_human(tool_name, arguments)   # your policy/UI here

# any of the six call sites accepts approval_hook=...
factory.for_call(call, approval_hook=SlackPrompt())
```

`ToolFactory.for_call` (and therefore `ToolInvocation`, `ParallelToolExecutor`,
`ParallelToolCaller`, `ToolChain`, `ReActStepExecutor` — every place a tool
knot is constructed for a call) wires a
`pirn_agents.agent.tool_approval_check.ToolApprovalCheck` (a core `Check`)
behind a core `Gate` in front of the call whenever the capability requires
approval; an unrestricted capability is never gated at all, so this costs
nothing when unused. **A denial is a core `Skipped`, not an error:** the
tool's own `process()` is never invoked, and the `ToolResult` view a caller
or the model reads back has a `Skipped` `outcome`, `status == "skipped"`, and
`error = "call skipped: approval denied"` — the model is told the call was
skipped, not that it failed. Passing no `approval_hook` uses the base
`ApprovalHook`, which auto-approves — the zero-cost default until a human-
in-the-loop surface is wired in.

### Filesystem
All paths resolve against the bound `root`; absolute paths, `..` traversal, and
symlink components are rejected, and reads/listings/globs are capped. Symlinks that
would escape the root are excluded from `glob` results.

### Web (`http_request`)
Before any request the target hostname is resolved and rejected if it lands on a
private, loopback, link-local, reserved, or multicast IP (this blocks the cloud
metadata endpoint). An optional `allowed_hosts` allowlist narrows further, and the
response body is streamed and truncated at `max_bytes`. `allow_private=True` is an
explicit opt-in for trusted internal endpoints only.

### `sql_query` — configuration and read-only guarantees
Bind it to a `SqlConnector` and its policy:

```python
import sqlite3
from pirn_agents.tools.sql.sql_query_tool import SqlQueryTool
from pirn_agents.tools.sql.sqlite_connector import SqliteConnector

conn = sqlite3.connect("app.db", check_same_thread=False)   # runs on a worker thread
tool = SqlQueryTool.bind(connector=SqliteConnector(connection=conn), read_only=True, max_rows=500)
```

- **`read_only=True`** (default) rejects any statement that is not a single
  `SELECT`/`WITH`, and rejects stacked statements and DML/DDL keywords
  (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `PRAGMA`, …).
- **`max_rows`** caps returned rows; the result carries `truncated=True` when hit.
- **Parameters** are passed positionally to the driver (parameterized queries).
- **Async driver:** `AiosqliteConnector` lazily imports `aiosqlite`
  (`pip install "pirn-agents[sql]"`); the stdlib `SqliteConnector` needs no extra.

> **Scope of the write guard.** The read-only check is a conservative *syntactic*
> guard, not a full SQL parser, and not a substitute for database permissions. For
> untrusted input, also connect with a least-privilege, read-only database role.

### Sandbox (`python_exec` / `shell`) — OD-1
Code/command execution is **opt-in and disabled by default**. Tools bound to a
`SandboxExecutor` raise `SandboxDisabledError` unless it was constructed with
`enabled=True`:

```python
from pirn_agents.tools.bundles import Bundles
from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor

executor = SandboxExecutor(enabled=True, timeout=5.0, max_output_bytes=65536)
tools = Bundles.sandbox_toolset(executor=executor)
```

The default `SubprocessSandboxBackend` enforces a **hard timeout** (killing the
child's whole process group) and **output truncation**. It does *not* provide
filesystem/network/syscall isolation — a subprocess runs with the host process's
privileges. For untrusted code, inject a stronger `SandboxBackend`
(container/VM/gVisor). This is why the sandbox is opt-in.
