"""``ExtractedEntity`` — one typed entity produced by schema-guided extraction.

The pydantic unit the F20 structured-output path decodes an LLM's entity
mentions into. Each entity carries a stable ``id`` (used to wire relations),
a ``type`` drawn from the target schema, a human-readable ``name``, and optional
scalar ``properties``. It converts one-to-one into a
:class:`~pirn_agents.graph_stores.graph_node.GraphNode` at upsert time.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    """A single typed entity extracted from source text.

    Attributes
    ----------
    id:
        Stable identifier used to reference this entity from relations.
    type:
        The entity type; must be one of the target schema's entity types.
    name:
        The entity's surface name / label.
    properties:
        Optional additional scalar properties.
    """

    id: str
    type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
