"""An immutable, ordered registry of uniquely-named :class:`Tool`s.

A :class:`Toolset` gathers the tools an agent may call into a single,
order-preserving collection keyed by unique ``name``. It offers
name lookup, membership, iteration, and a provider-neutral
:meth:`schema` export that a downstream codec adapts per LLM provider.

Like :class:`Tool`, a toolset is opaque to pydantic (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); its audit form is
the ordered list of tool names, keeping content-addressing stable.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tool import Tool


class Toolset(PirnOpaqueValue):
    """An ordered collection of :class:`Tool`s with unique names."""

    def __init__(self, tools: Sequence[Tool] = ()) -> None:
        """Build a toolset from ``tools``, preserving order.

        Raises
        ------
        TypeError
            If any element is not a :class:`Tool`; the message names the
            offending index and its actual type.
        ValueError
            If two tools share the same ``name``; the message names the
            duplicate.
        """
        ordered: list[Tool] = []
        by_name: dict[str, Tool] = {}
        for index, tool in enumerate(tools):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"tools[{index}] must be a Tool, got {type(tool).__name__}"
                )
            if tool.name in by_name:
                raise ValueError(f"duplicate tool name: {tool.name!r}")
            by_name[tool.name] = tool
            ordered.append(tool)
        self._tools: tuple[Tool, ...] = tuple(ordered)
        self._by_name: dict[str, Tool] = by_name

    def get(self, name: str) -> Tool | None:
        """Return the tool registered under ``name``, or ``None``."""
        return self._by_name.get(name)

    def __contains__(self, name: object) -> bool:
        """Return whether a tool named ``name`` is registered."""
        return name in self._by_name

    def __iter__(self) -> Iterator[Tool]:
        """Iterate tools in insertion order."""
        return iter(self._tools)

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def merge(self, other: Toolset) -> Toolset:
        """Return a new toolset concatenating ``self`` then ``other``.

        Order is preserved and uniqueness is re-checked across both
        sets; a name present in both raises :class:`ValueError`.
        """
        return Toolset((*self._tools, *other._tools))

    def __add__(self, other: Toolset) -> Toolset:
        """Alias for :meth:`merge` supporting the ``+`` operator."""
        return self.merge(other)

    def schema(self) -> list[dict[str, Any]]:
        """Return a provider-neutral tool-schema list, one dict per tool.

        Each entry has the stable, provider-agnostic shape
        ``{"name": ..., "description": ..., "parameters": {...}}``. No
        provider-specific wrapping is applied; that is the job of the
        per-provider codec (F1-S5).
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters_schema),
            }
            for tool in self._tools
        ]

    def _pirn_audit_dict(self) -> Any:
        """Return the ordered list of registered tool names."""
        return [tool.name for tool in self._tools]
