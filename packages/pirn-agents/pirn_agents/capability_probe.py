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
        ``qdrant``, ``pgvector``, ``chroma``, ``neo4j``, ``kuzu``, ``local-embed``,
        ``cross-encoder``, ``web``, ``mcp``, ``sql``, ``postgres``, ``s3``, ``otel``,
        ``grammar``, ``pdf``, ``docx``, ``html``, ``ragas`` and
        bundles ``llm``, ``vector``, ``all``) whose values report whether that
        extra is importable here.
    """
    leaf_modules: dict[str, str] = {
        "openai": "openai",
        "anthropic": "anthropic",
        "qdrant": "qdrant_client",
        "pgvector": "asyncpg",
        "chroma": "chromadb",
        "neo4j": "neo4j",
        "kuzu": "kuzu",
        "local-embed": "sentence_transformers",
        "cross-encoder": "sentence_transformers",
        "web": "httpx",
        "mcp": "mcp",
        "sql": "aiosqlite",
        "postgres": "asyncpg",
        "s3": "aioboto3",
        "otel": "opentelemetry",
        "grammar": "outlines",
        "pdf": "pypdf",
        "docx": "docx",
        "html": "bs4",
        "ragas": "ragas",
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
