"""``GraphEdge`` — one upsertable (id, source, target, type, properties) edge.

The neutral write/read unit every
:class:`~pirn_agents.graph_stores.graph_store.GraphStore` accepts and returns for
relationships. Frozen and opaque. When no explicit ``id`` is supplied,
:meth:`create` derives a deterministic one from ``source_id``, ``type``, and
``target_id`` so re-extracting the same relationship upserts idempotently.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class GraphEdge(PirnOpaqueValue):
    """A single directed graph relationship.

    Attributes
    ----------
    id:
        Stable primary key; upserting an existing ``id`` overwrites it.
    source_id:
        The id of the node the edge points *from*.
    target_id:
        The id of the node the edge points *to*.
    type:
        The relationship type (e.g. ``"WORKS_AT"``).
    properties:
        Arbitrary scalar properties used for filtering and rendering.
    """

    id: str
    source_id: str
    target_id: str
    type: str
    properties: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        target_id: str,
        type: str,
        id: str | None = None,
        properties: Mapping[str, Any] | None = None,
    ) -> GraphEdge:
        """Build an edge, deriving a deterministic ``id`` when none is given.

        Args:
            source_id: The id of the source node.
            target_id: The id of the target node.
            type: The relationship type.
            id: Optional explicit edge id; when ``None`` a deterministic id
                ``"{source_id}|{type}|{target_id}"`` is used.
            properties: Optional property mapping; defaults to empty.

        Returns:
            A frozen :class:`GraphEdge`.

        Raises:
            TypeError: If ``source_id``, ``target_id``, or ``type`` is not a
                non-empty string.
        """
        if not isinstance(source_id, str) or not source_id:
            raise TypeError(f"GraphEdge: source_id must be a non-empty str, got {source_id!r}")
        if not isinstance(target_id, str) or not target_id:
            raise TypeError(f"GraphEdge: target_id must be a non-empty str, got {target_id!r}")
        if not isinstance(type, str) or not type:
            raise TypeError(f"GraphEdge: type must be a non-empty str, got {type!r}")
        edge_id = id if id is not None else f"{source_id}|{type}|{target_id}"
        return cls(
            id=edge_id,
            source_id=source_id,
            target_id=target_id,
            type=type,
            properties=dict(properties) if properties is not None else {},
        )
