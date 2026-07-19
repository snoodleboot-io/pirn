"""Derive a JSON-Schema ``parameters`` object from a ``SubTapestry`` agent.

An :class:`~pirn_agents.agent_tool.AgentTool` needs a ``parameters_schema`` so a
planner knows what to pass. This module derives one from the agent's
``process`` signature, reusing the same annotation→JSON-Schema mapping the
``@tool`` decorator uses for plain functions. Dependency parameters (the LLM
provider, tools, memory, and other injected collaborators) are filtered out so
the schema exposes only the caller-facing task inputs. When the agent declares
no such inputs the schema falls back to the conventional ``{task: str}``.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.providers.embedding_provider import EmbeddingProvider
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.memory_store import MemoryStore
from pirn_agents.tool import Tool
from pirn_agents.tool_schema_compiler import ToolSchemaCompiler


def _is_dependency(name: str, annotation: Any) -> bool:
    """Return whether a ``process`` parameter is an injected collaborator.

    Collaborators (provider/tools/memory/etc.) are recognised either by a
    conventional parameter name or by an annotation referencing a known
    provider/tool interface, and are excluded from the caller-facing schema.
    """
    dependency_names = {
        "llm",
        "tools",
        "tool",
        "search_tool",
        "specialists",
        "memory",
        "memory_store",
        "embedder",
        "embedding_provider",
        "provider",
        "messages",
    }
    if name in dependency_names:
        return True
    dependency_types = (LLMProvider, Tool, MemoryStore, EmbeddingProvider, Knot)
    if isinstance(annotation, type) and issubclass(annotation, dependency_types):
        return True
    origin = getattr(annotation, "__origin__", None)
    args: tuple[Any, ...] = getattr(annotation, "__args__", ()) or ()
    if origin in (list, tuple, Sequence):
        return any(isinstance(arg, type) and issubclass(arg, dependency_types) for arg in args)
    return False


def default_agent_schema() -> dict[str, Any]:
    """Return the conventional single-``task`` schema for an input-less agent."""
    return {
        "type": "object",
        "properties": {"task": {"type": "string"}},
        "required": ["task"],
    }


def derive_agent_schema(agent: object) -> Mapping[str, Any]:
    """Derive a JSON-Schema ``parameters`` object from ``agent.process``.

    Every non-dependency parameter of the agent's ``process`` method becomes a
    schema property; parameters without a default are marked required. When no
    caller-facing parameters remain, :func:`default_agent_schema` is returned.

    Args:
        agent: The ``SubTapestry`` agent to introspect.

    Returns:
        A JSON-Schema object describing the agent's task inputs.
    """
    process = getattr(type(agent), "process", None)
    if process is None:
        return default_agent_schema()
    try:
        signature = inspect.signature(process)
        hints = inspect.get_annotations(process, eval_str=True)
    except (TypeError, ValueError, NameError):
        return default_agent_schema()

    compiler = ToolSchemaCompiler()
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    for name, parameter in signature.parameters.items():
        if name in ("self", "cls"):
            continue
        if parameter.kind in (
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        ):
            continue
        annotation = hints.get(name, parameter.annotation)
        if _is_dependency(name, annotation):
            continue
        properties[name] = dict(compiler.annotation_to_schema(annotation))
        if parameter.default is inspect.Parameter.empty:
            required.append(name)

    if not properties:
        return default_agent_schema()
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema
