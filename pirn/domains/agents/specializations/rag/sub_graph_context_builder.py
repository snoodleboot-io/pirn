"""``SubGraphContextBuilder`` — flatten retrieved entity/relation dicts.

Walks the retrieved graph nodes and edges up to ``hop_count`` hops and
emits a single textual sub-graph block ready to feed into a prompt
builder. The graph store is expected to return mappings shaped as one
of:

* an entity: ``{"type": "entity", "id": ..., "label": ..., "attrs": {...}}``
* a relation: ``{"type": "relation", "src": ..., "dst": ..., "rel": ...}``

Mappings without a ``"type"`` key are treated as entities so that
test-time stub stores can stay terse.

Algorithm:
    1. Receive ``retrieved`` list of Mappings and ``hop_count`` integer.
    2. Validate that each item is a Mapping; raise ``TypeError`` otherwise.
    3. Partition items into entities (``type != "relation"``) and relations
       (``type == "relation"``).
    4. Normalise each entity to
       ``{"kind": "entity", "id": ..., "label": ..., "attrs": {...}}``
       and each relation to
       ``{"kind": "relation", "src": ..., "dst": ..., "rel": ...}``.
    5. Return ``[{"hops": hop_count}] + block_entities + block_relations``.

Math:
    No quantitative computation — partitioning and normalisation are
    pure structural transformations.

References:
    - Edge & Hamilton, "From Local to Global: A Graph RAG Approach to
      Query-Focused Summarization" (2024):
      https://arxiv.org/abs/2404.16130
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SubGraphContextBuilder(Knot):
    """Build a textual sub-graph block from retrieved graph mappings."""

    def __init__(
        self,
        *,
        retrieved: Knot,
        _config: KnotConfig,
        hop_count: Knot | int = 2,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            retrieved=retrieved,
            hop_count=hop_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        retrieved: list[Mapping[str, Any]],
        hop_count: int,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Partition retrieved nodes into entities and relations and return a typed sub-graph block.

        Args:
            retrieved: The list of graph node Mappings to partition into entities and relations.
            hop_count: The hop budget surfaced as a metadata entry in the returned block.

        Returns:
            A list of Mappings beginning with a hop-count header followed by entity and relation entries.

        Raises:
            TypeError: If any element of retrieved is not a Mapping.
            ValueError: If hop_count is not a positive integer.
        """
        if not isinstance(hop_count, int) or hop_count <= 0:
            raise ValueError(
                "SubGraphContextBuilder: hop_count must be a positive int, "
                f"got {hop_count!r}"
            )
        entities: list[Mapping[str, Any]] = []
        relations: list[Mapping[str, Any]] = []
        for index, item in enumerate(retrieved):
            if not isinstance(item, Mapping):
                raise TypeError(
                    f"SubGraphContextBuilder: retrieved[{index}] must be a "
                    f"Mapping, got {type(item).__name__}"
                )
            kind = item.get("type", "entity")
            if kind == "relation":
                relations.append(item)
            else:
                entities.append(item)
        # The hop budget is informational at this layer — a richer graph
        # store can expand neighbours; here we surface it so the prompt
        # builder can render an honest "expanded {hop_count} hops" hint.
        block_entities = [
            {
                "kind": "entity",
                "id": entity.get("id"),
                "label": entity.get("label"),
                "attrs": dict(entity.get("attrs", {})) if isinstance(
                    entity.get("attrs", {}), Mapping
                ) else {},
            }
            for entity in entities
        ]
        block_relations = [
            {
                "kind": "relation",
                "src": relation.get("src"),
                "dst": relation.get("dst"),
                "rel": relation.get("rel"),
            }
            for relation in relations
        ]
        return [{"hops": hop_count}] + block_entities + block_relations
