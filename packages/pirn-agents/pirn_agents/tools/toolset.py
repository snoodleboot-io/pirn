"""An immutable, ordered registry of uniquely-named tool capabilities.

A :class:`Toolset` gathers the capabilities an agent may call into a single,
order-preserving collection keyed by unique ``name``. Every entry is a
:class:`~pirn_agents.tools.tool_factory.ToolFactory`; anything
:meth:`ToolFactory.of` accepts — a ``Tool`` class, a ``@tool``/``@KnotFactory.knot``
factory, a configured knot, or (deprecated) an ``invoke``-shaped ``Tool``
instance — is normalised on the way in, so ``Toolset([CalculatorTool,
ReadFileTool.bind(root="/srv")])`` and ``toolset.get("read_file")`` speak one
type.  It offers name lookup, membership, iteration, and a provider-neutral
:meth:`schema` export that a downstream codec adapts per LLM provider.

Like a factory, a toolset is opaque to pydantic (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); its audit form is
the ordered list of tool names, keeping content-addressing stable.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.tools.tool_declaration import ToolDeclaration
from pirn_agents.tools.tool_factory import ToolFactory


class Toolset(PirnOpaqueValue):
    """An ordered collection of :class:`ToolFactory` capabilities with unique names."""

    def __init__(self, tools: Sequence[Any] = ()) -> None:
        """Build a toolset from ``tools``, preserving order.

        Raises
        ------
        TypeError
            If any element is not a capability :meth:`ToolFactory.of` accepts;
            the message names the offending index and its actual type.
        ValueError
            If two tools share the same ``name``; the message names the
            duplicate.
        """
        ordered: list[ToolFactory] = []
        by_name: dict[str, ToolFactory] = {}
        for index, candidate in enumerate(tools):
            try:
                factory = ToolFactory.of(candidate)
            except TypeError as exc:
                raise TypeError(
                    f"tools[{index}] must be a tool capability (a Tool class, a ToolFactory or "
                    f"a knot), got {type(candidate).__name__}"
                ) from exc
            if factory.name in by_name:
                raise ValueError(f"duplicate tool name: {factory.name!r}")
            by_name[factory.name] = factory
            ordered.append(factory)
        self._tools: tuple[ToolFactory, ...] = tuple(ordered)
        self._by_name: dict[str, ToolFactory] = by_name

    def get(self, name: str) -> ToolFactory | None:
        """Return the capability registered under ``name``, or ``None``."""
        return self._by_name.get(name)

    def __contains__(self, name: object) -> bool:
        """Return whether a tool named ``name`` is registered."""
        return name in self._by_name

    def __iter__(self) -> Iterator[ToolFactory]:
        """Iterate capabilities in insertion order."""
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

    def declarations(self) -> tuple[ToolDeclaration, ...]:
        """Return one :class:`ToolDeclaration` per tool, in registration order.

        The typed counterpart of :meth:`schema` for in-process callers, who
        can read ``declaration.name`` instead of indexing a dict.
        """
        return tuple(tool.declaration() for tool in self._tools)

    def schema(self) -> list[dict[str, Any]]:
        """Return a provider-neutral tool-schema list, one dict per tool.

        Each entry has the stable, provider-agnostic shape
        ``{"name": ..., "description": ..., "parameters": {...}}``. No
        provider-specific wrapping is applied; that is the job of the
        per-provider codec (F1-S5). This is the serialised form of
        :meth:`declarations`, and is what a
        :class:`pirn_agents.llm.provider_adapter.ProviderAdapter` consumes.
        """
        return [declaration.to_payload() for declaration in self.declarations()]

    def _pirn_audit_dict(self) -> Any:
        """Return the ordered list of registered tool names."""
        return [tool.name for tool in self._tools]
