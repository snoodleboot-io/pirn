# Packaging & extras matrix (pirn-agents)

`pirn-agents` ships with a deliberately small base wheel. All optional backends
(LLM providers, vector stores, HTTP fetching, MCP) are **lazily imported** at the
point of use, so the base install pulls in `pirn-core` only. You add exactly the
extras you use — nothing more.

## OD-4 rationale (lazy backends → small base wheel)

- Backend imports happen inside functions, not at module import time. Importing
  `pirn_agents` never requires a provider SDK.
- Missing-backend errors are raised with an actionable install hint at call time
  (e.g. the document loader tells you to install the HTTP backend when it needs
  `httpx`).
- Result: a lean default install, faster resolution, and no unused transitive
  dependencies for users who only need a subset of capabilities.

## Provider neutrality

This project treats every LLM/vendor provider **equally**. The per-provider
extras below are **illustrative** examples of connector backends and are listed
as equal siblings. No vendor is privileged in ordering, defaults, or bundling.
The base install never depends on any provider.

## Extras matrix

### Per-provider (illustrative, equal siblings)

| Extra | Installs |
|-------------|--------------------|
| `openai` | `openai>=1.0` |
| `anthropic` | `anthropic>=0.40` |
| `qdrant` | `qdrant-client>=1.7` |

### Capability bundles

| Bundle | Composes | Purpose |
|----------|-----------------------------------|----------------------------|
| `llm` | `openai`, `anthropic` | LLM provider backends |
| `vector` | `qdrant` | vector-store backends |
| `web` | `httpx>=0.27` | http(s) document fetching |
| `mcp` | `mcp>=1.0` | Model Context Protocol |
| `all` | `llm`, `vector`, `web`, `mcp` | everything |

Bundles use PEP 621 self-referential extra composition
(`pirn-agents[openai]`), so a bundle stays in sync with the extras it groups.

## Install examples

```bash
pip install pirn-agents                 # base: pirn-core only
pip install "pirn-agents[web]"          # + httpx for http(s) document sources
pip install "pirn-agents[llm]"          # + LLM provider backends
pip install "pirn-agents[all]"          # every optional backend
```

## Graceful degradation with `available_extras()`

Because backends are optional, application code should not assume a connector's
SDK is installed. :func:`pirn_agents.available_extras` reports which extras are
importable in the current environment. It probes with
`importlib.util.find_spec`, so it **never imports a backend and never raises** —
importing `pirn_agents` and calling this function stays cheap and side-effect
free.

```python
import pirn_agents

extras = pirn_agents.available_extras()
# e.g. {"openai": False, "anthropic": False, "qdrant": True, "web": True,
#       "mcp": False, "llm": False, "vector": True, "all": False}

if extras["qdrant"]:
    # backend present: construct the vector connector for real
    store = build_vector_store()
else:
    # backend absent: degrade gracefully instead of crashing at import time
    logger.info("vector extra not installed; falling back to in-memory store")
    store = build_in_memory_store()
```

The returned mapping covers every extra name — the per-provider leaves
(`openai`, `anthropic`, `qdrant`, `web`, `mcp`) and the capability bundles
(`llm`, `vector`, `all`). A bundle is reported available only when **all** of
its leaves are importable, so `extras["llm"]` is `True` only if every LLM
provider backend it groups is installed. Values reflect what is actually
installed, letting you skip, fall back, or surface an install hint per
capability. This example is provider-neutral: swap `qdrant` for any extra your
code depends on.

