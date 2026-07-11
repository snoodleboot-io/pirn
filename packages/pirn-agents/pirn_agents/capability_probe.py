"""Capability probing for optional backend extras.

``pirn-agents`` ships a small base wheel; every optional backend (LLM
providers, vector stores, HTTP fetching, MCP) is an *extra* that is lazily
imported at the point of use. :func:`available_extras` lets callers discover
which extras are importable in the current environment WITHOUT importing any
backend and WITHOUT raising, so applications can degrade gracefully.

See ``pirn_agents/PACKAGING.md`` for the extras matrix and a graceful-
degradation example.
"""

from __future__ import annotations

import importlib.util


def _is_importable(module: str) -> bool:
    """Return whether ``module`` can be imported, without importing it.

    Uses :func:`importlib.util.find_spec`, which inspects the import system
    without executing the module. ``find_spec`` may itself raise (e.g.
    ``ModuleNotFoundError`` when a *parent* package is missing), so any
    exception is treated as "not available".
    """
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def available_extras() -> dict[str, bool]:
    """Map every optional extra name to its import availability.

    Leaf extras map to a single representative importable module; bundle
    extras are available iff all of their leaves are. Probing never imports a
    backend and never raises.

    Returns:
        A dict keyed by every extra name (leaves ``openai``, ``anthropic``,
        ``qdrant``, ``pgvector``, ``chroma``, ``local-embed``, ``cross-encoder``,
        ``web``, ``mcp``, ``otel`` and bundles ``llm``, ``vector``, ``all``) whose
        values report whether that extra is importable here.
    """
    leaf_modules: dict[str, str] = {
        "openai": "openai",
        "anthropic": "anthropic",
        "qdrant": "qdrant_client",
        "pgvector": "asyncpg",
        "chroma": "chromadb",
        "local-embed": "sentence_transformers",
        "cross-encoder": "sentence_transformers",
        "web": "httpx",
        "mcp": "mcp",
        "otel": "opentelemetry",
    }
    leaves: dict[str, bool] = {
        extra: _is_importable(module) for extra, module in leaf_modules.items()
    }

    bundles: dict[str, bool] = {
        "llm": leaves["openai"] and leaves["anthropic"],
        "vector": leaves["qdrant"] and leaves["pgvector"] and leaves["chroma"],
        "all": all(leaves.values()),
    }

    return {**leaves, **bundles}
