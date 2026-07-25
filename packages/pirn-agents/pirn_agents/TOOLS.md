# Base Tool Library (PAE-F6)

A curated set of production-grade `Tool` implementations agents can use out of
the box — the "batteries" for the batteries-included runtime. Every tool is a
`Tool` subclass, derives a provider-neutral JSON schema, and returns a typed F1
`ToolResult` via `as_tool_result(call)`. Optional backends (`httpx`, `aiosqlite`)
are imported lazily at call time, so `import pirn_agents` stays backend-free.

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
defaults. They only *construct* tools, so importing them triggers no backend
imports:

```python
from pirn_agents.tools.bundles import (
    calculator_toolset, web_toolset, filesystem_toolset,
    data_toolset, retrieval_toolset, sandbox_toolset,
)

tools = calculator_toolset() + web_toolset() + filesystem_toolset(root="/srv/workspace")
```

`Toolset` supports `+` / `merge` (unique names re-checked), `get(name)`,
iteration, and `schema()` (provider-neutral schema list).

## Registering a Toolset with a ReActLoop

```python
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.tools.bundles import calculator_toolset, retrieval_toolset
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.agent_message import AgentMessage

toolset = calculator_toolset() + retrieval_toolset(store=my_store)

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

Under F1 schema-based tool calling, pass a `ToolCall` to `tool.as_tool_result(call)`
(or dispatch a batch through `ParallelToolExecutor`). The text ReAct loop supplies
each action input as `{"input": ...}`; single-argument base tools accept that as an
alias for their canonical parameter, so the same tool works both ways.

## Security notes

### Filesystem
All paths resolve against the injected `root`; absolute paths, `..` traversal, and
symlink components are rejected, and reads/listings/globs are capped. Symlinks that
would escape the root are excluded from `glob` results.

### Web (`http_request`)
Before any request the target hostname is resolved and rejected if it lands on a
private, loopback, link-local, reserved, or multicast IP (this blocks the cloud
metadata endpoint). An optional `allowed_hosts` allowlist narrows further, and the
response body is streamed and truncated at `max_bytes`. `allow_private=True` is an
explicit opt-in for trusted internal endpoints only.

### `sql_query` — configuration and read-only guarantees
Configure it with a `SqlConnector` and its policy:

```python
import sqlite3
from pirn_agents.tools.sql.sql_query_tool import SqlQueryTool
from pirn_agents.tools.sql.sqlite_connector import SqliteConnector

conn = sqlite3.connect("app.db", check_same_thread=False)   # runs on a worker thread
tool = SqlQueryTool(connector=SqliteConnector(connection=conn), read_only=True, max_rows=500)
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
Code/command execution is **opt-in and disabled by default**. Tools backed by a
`SandboxExecutor` raise `SandboxDisabledError` unless it was constructed with
`enabled=True`:

```python
from pirn_agents.tools.bundles import sandbox_toolset
from pirn_agents.tools.sandbox.sandbox_executor import SandboxExecutor

executor = SandboxExecutor(enabled=True, timeout=5.0, max_output_bytes=65536)
tools = sandbox_toolset(executor=executor)
```

The default `SubprocessSandboxBackend` enforces a **hard timeout** (killing the
child's whole process group) and **output truncation**. It does *not* provide
filesystem/network/syscall isolation — a subprocess runs with the host process's
privileges. For untrusted code, inject a stronger `SandboxBackend`
(container/VM/gVisor). This is why the sandbox is opt-in.
