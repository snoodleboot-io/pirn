"""``RouteTable`` — an opaque name→:class:`MemoryStore` routing map.

Router RAG dispatches a query to one of several named indexes/strategies. The
candidate stores are bundled in a :class:`RouteTable` so the whole map travels
through the pirn graph as a single opaque config value (pydantic validates it by
``isinstance`` only, exactly like a bare :class:`MemoryStore`), instead of a
plain ``dict`` of opaque values that pydantic would try to descend into.
"""

from __future__ import annotations

from collections.abc import Mapping

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory_store import MemoryStore


class RouteTable(PirnOpaqueValue):
    """Immutable mapping of route name to the :class:`MemoryStore` for that route."""

    def __init__(self, routes: Mapping[str, MemoryStore]) -> None:
        """Bundle named stores into a route table.

        Args:
            routes: A non-empty mapping of route name to its backing store.

        Raises:
            ValueError: If ``routes`` is empty.
            TypeError: If any value is not a :class:`MemoryStore`.
        """
        if not routes:
            raise ValueError("RouteTable: routes must be a non-empty mapping")
        for name, store in routes.items():
            if not isinstance(store, MemoryStore):
                raise TypeError(
                    f"RouteTable: route {name!r} must map to a MemoryStore, "
                    f"got {type(store).__name__}"
                )
        self._routes: dict[str, MemoryStore] = dict(routes)

    def route_names(self) -> list[str]:
        """Return the route names in insertion order."""
        return list(self._routes)

    def has(self, name: str) -> bool:
        """Return whether ``name`` is a known route."""
        return name in self._routes

    def store_for(self, name: str) -> MemoryStore:
        """Return the store bound to ``name``.

        Raises:
            KeyError: If ``name`` is not a known route.
        """
        if name not in self._routes:
            raise KeyError(f"RouteTable: unknown route {name!r}")
        return self._routes[name]
