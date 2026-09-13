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
from pirn_agents.types.messaging.agent_message import AgentMessage

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

## Replay identity

A tool used as a knot input (for example by `ToolInvocation` or `ToolExecutor`)
is part of the lineage row's content hash. Replay compares that hash, so it
decides whether a recorded tool call can be served instead of running the tool
again.

By default a tool is **identity-keyed**. Its hash is unique to the instance and
the process, so a run recorded in one process refuses to replay in another
(`ReplayMismatchError`). This is the safe direction for any tool whose behaviour
depends on something the hash can't see, such as a connection, store, client, or
sandbox.

A tool **opts in** to content identity by overriding `content_identity()` to
return its declared configuration. Its hash then covers its class, `name`,
`description`, `parameters_schema` and that configuration, so equal tools hash
equal in every process and their recorded calls replay.

| Tool | Identity | Declared config |
|------|----------|-----------------|
| `CalculatorTool` | content | none |
| `ReadFileTool` / `WriteFileTool` | content | resolved absolute `root`, `max_bytes` |
| `ListDirTool` | content | resolved absolute `root`, `max_entries` |
| `GlobTool` | content | resolved absolute `root`, `max_results` |
| `HtmlToTextTool` | content | `max_chars` |
| `HttpRequestTool` | content, **identity if `client` or `resolver` is injected** | sorted `allowed_hosts`, `allow_private`, `max_bytes`, `timeout`, `connect_timeout` |
| `@tool` functions | content, under the conditions below | function `module.qualname`, `args_model`, `return_schema`, permissions, async/streaming/stateful flags, canonical `state` |
| `SqlQueryTool`, `RetrieverTool`, `RagTool`, `WebSearchTool`, `McpTool`, `PythonExecTool`, `ShellTool`, `AgentTool`, `StubTool` | identity | — (they hold live resources) |

A `@tool` function is content-identified only when all of these hold:

- It is a plain function that its module still binds by name. A lambda, a
  `<locals>` closure, a bound method, a `functools.partial`, a callable object, or
  a shadowed definition stays identity-keyed.
- It has no closure and no `__wrapped__`, so a `functools.wraps` decorator (which
  copies the qualname and can hide config in its closure) keeps the tool
  identity-keyed.
- Every default argument value is plain data (`None`, `bool`, `int`, `float`,
  `str`, or lists, tuples and str-keyed dicts of those). The defaults are part of
  the hash, because the schema does not carry them.
- No custom `args_validator` was passed. A validator derived from `args_model` is
  fine, and any `args_model` must itself have a unique name.
- Any injected `state` defines `__pirn_canonical__`, so its author has declared
  what identifies it. Plain state, such as a dict or a connection, keeps the tool
  identity-keyed.
- If it is defined in `__main__`, the running script has a file. The resolved
  absolute script path is part of the identity, so a different script defining
  the same name refuses. A REPL, notebook or `python -c` stays identity-keyed.

The same naming rules apply to tool classes. A class defined inside a function
(`<locals>`), a shadowed class, or a `__main__` class with no script file stays
identity-keyed.

The opt-in is **not inherited**. A subclass of an opted-in tool is identity-keyed
until it re-declares `content_identity()` with its own configuration.

Accepted limits: the function body and any module globals it reads are not
hashed. An edited body, or a changed global, at an unchanged module path or script
path still matches and serves the older result, the same as for a knot's
`process`. `HttpRequestTool` doesn't hash the proxy or TLS settings `httpx` reads
from the environment.

`Toolset` and `RouteCandidate` hash through their tools' own identities.

**Rules for opting in a new tool:**

1. Return **every** constructor input that changes behaviour, as JSON-friendly
   primitives.
2. Never return a credential, token, header, or URL userinfo/query string.
3. Return `None` for any instance whose behaviour depends on an injected object
   that has no content form.
4. Add a case to `tests/tools/test_tool_identity_gate.py`. The gate varies each
   constructor argument and fails if the hash doesn't change. It also fails for
   any opted-in class anywhere in the workspace that has no case, and for any
   subclass of an opted-in tool that neither re-declares the opt-in nor is listed
   as intentionally identity-keyed.

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
