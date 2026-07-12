"""``GraphNode`` — one upsertable (id, type, properties) graph vertex.

The neutral write/read unit every
:class:`~pirn_agents.graph_stores.graph_store.GraphStore` accepts and returns for
vertices. Frozen and opaque so it travels through the pirn graph without entering
the content-addressed hash by value; ``properties`` is normalised to a plain dict
by :meth:`create`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class GraphNode(PirnOpaqueValue):
    """A single graph vertex.

    Attributes
    ----------
    id:
        Stable primary key; upserting an existing ``id`` overwrites it.
    type:
        The node's label / type (e.g. ``"Person"``), used for typed queries.
    properties:
        Arbitrary scalar properties used for equality filtering and rendering.
    """

    id: str
    type: str
    properties: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        id: str,
        type: str,
        properties: Mapping[str, Any] | None = None,
    ) -> GraphNode:
        """Build a node, copying ``properties`` into a plain dict.

        Args:
            id: The node primary key.
            type: The node label / type.
            properties: Optional property mapping; defaults to empty.

        Returns:
            A frozen :class:`GraphNode`.

        Raises:
            TypeError: If ``id`` or ``type`` is not a non-empty string.
        """
        if not isinstance(id, str) or not id:
            raise TypeError(f"GraphNode: id must be a non-empty str, got {id!r}")
        if not isinstance(type, str) or not type:
            raise TypeError(f"GraphNode: type must be a non-empty str, got {type!r}")
        return cls(
            id=id,
            type=type,
            properties=dict(properties) if properties is not None else {},
        )
