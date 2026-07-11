"""``ToolRegistry`` — a discoverable, namespaced, versioned registry of tools.

The registry is the lookup layer of the tool SDK: tools register under a
``(namespace, name, version)`` key and are retrieved in **O(1)** by that key, or
by ``(namespace, name)`` with automatic resolution to the latest version. From
the registry a :class:`~pirn_agents.toolset.Toolset` can be *composed* by
querying a namespace and/or tags, so an agent's available tools are assembled
dynamically rather than hand-listed.

The registry layers over :class:`sweet_tea.registry.Registry`: every registered
tool's concrete type is mirrored into the shared sweet_tea registry (keyed by
tool name, with the namespace as ``library`` and the version as ``label``) so
tools participate in the same discovery mechanism as the rest of the knot
library, while instance-level lookup stays a direct dict access here.

Versions are compared as dotted numeric tuples (``"1.10.0" > "1.9.0"``) with a
lexical fallback for non-numeric labels.
"""

from __future__ import annotations

from collections.abc import Iterable

from sweet_tea.registry import Registry as SweetTeaRegistry

from pirn_agents.tool import Tool
from pirn_agents.toolset import Toolset


def _version_key(version: str) -> tuple[tuple[int, str], ...]:
    """Return a sortable key for a dotted ``version`` string.

    Each dotted part sorts numerically when it is all digits and lexically
    otherwise, so ``"1.10.0"`` orders after ``"1.9.0"``.
    """
    parts: list[tuple[int, str]] = []
    for part in version.split("."):
        if part.isdigit():
            parts.append((int(part), ""))
        else:
            parts.append((-1, part))
    return tuple(parts)


class ToolRegistry:
    """A dynamic registry of tools keyed by namespace, name, and version."""

    def __init__(self, *, mirror_to_sweet_tea: bool = True) -> None:
        """Create an empty registry.

        Args:
            mirror_to_sweet_tea: When ``True`` (default) each registered tool's
                type is also registered with the shared
                :class:`sweet_tea.registry.Registry` for cross-library
                discovery. Set ``False`` to keep registration purely local.
        """
        self._by_key: dict[tuple[str, str, str], Tool] = {}
        self._versions: dict[tuple[str, str], list[str]] = {}
        self._tags: dict[tuple[str, str, str], frozenset[str]] = {}
        self._mirror_to_sweet_tea = mirror_to_sweet_tea

    def register(
        self,
        tool: Tool,
        *,
        namespace: str = "default",
        version: str = "1.0.0",
        tags: Iterable[str] = (),
    ) -> None:
        """Register ``tool`` under ``(namespace, tool.name, version)``.

        Raises
        ------
        TypeError
            If ``tool`` is not a :class:`Tool`.
        ValueError
            If the ``(namespace, name, version)`` key is already registered.
        """
        if not isinstance(tool, Tool):
            raise TypeError(f"tool must be a Tool, got {type(tool).__name__}")
        key = (namespace, tool.name, version)
        if key in self._by_key:
            raise ValueError(
                f"tool already registered: namespace={namespace!r} "
                f"name={tool.name!r} version={version!r}"
            )
        self._by_key[key] = tool
        self._tags[key] = frozenset(tags)
        versions = self._versions.setdefault((namespace, tool.name), [])
        versions.append(version)
        versions.sort(key=_version_key)
        if self._mirror_to_sweet_tea:
            SweetTeaRegistry.register(
                key=tool.name, class_def=type(tool), library=namespace, label=version
            )

    def get(
        self, name: str, *, namespace: str = "default", version: str | None = None
    ) -> Tool | None:
        """Return a registered tool, or ``None`` when no match exists.

        With ``version`` given the lookup is an exact O(1) key hit; without it
        the latest registered version in ``namespace`` is resolved.
        """
        if version is not None:
            return self._by_key.get((namespace, name, version))
        latest = self.latest_version(name, namespace=namespace)
        if latest is None:
            return None
        return self._by_key.get((namespace, name, latest))

    def latest_version(self, name: str, *, namespace: str = "default") -> str | None:
        """Return the highest registered version of ``name``, or ``None``."""
        versions = self._versions.get((namespace, name))
        if not versions:
            return None
        return versions[-1]

    def versions(self, name: str, *, namespace: str = "default") -> list[str]:
        """Return all registered versions of ``name``, lowest first."""
        return list(self._versions.get((namespace, name), []))

    def namespaces(self) -> list[str]:
        """Return the sorted list of namespaces holding at least one tool."""
        return sorted({namespace for namespace, _, _ in self._by_key})

    def __len__(self) -> int:
        """Return the number of registered ``(namespace, name, version)`` entries."""
        return len(self._by_key)

    def __contains__(self, key: object) -> bool:
        """Return whether a ``(namespace, name, version)`` tuple is registered."""
        return key in self._by_key

    def compose(
        self,
        *,
        namespace: str | None = None,
        tags: Iterable[str] | None = None,
    ) -> Toolset:
        """Compose a :class:`Toolset` from the registry by query.

        Filters by ``namespace`` (all namespaces when ``None``) and by ``tags``
        (a tool matches when it carries every requested tag). At most one tool
        per name is included — the latest version — so the resulting toolset has
        unique names. Tools are ordered by ``(namespace, name)``.
        """
        wanted_tags = frozenset(tags) if tags is not None else frozenset()
        chosen: dict[tuple[str, str], tuple[str, Tool]] = {}
        for (ns, name, version), tool in self._by_key.items():
            if namespace is not None and ns != namespace:
                continue
            if wanted_tags and not wanted_tags.issubset(self._tags[(ns, name, version)]):
                continue
            current = chosen.get((ns, name))
            if current is None or _version_key(version) > _version_key(current[0]):
                chosen[(ns, name)] = (version, tool)
        ordered = [tool for _, (_, tool) in sorted(chosen.items(), key=lambda item: item[0])]
        return Toolset(ordered)
