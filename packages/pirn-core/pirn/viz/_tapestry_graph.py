"""Data record for a scanned tapestry graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TapestryGraph:
    """Serializable description of a tapestry's nodes and edges."""

    name: str
    source: str
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "nodes": self.nodes,
            "edges": self.edges,
            "error": self.error,
        }
