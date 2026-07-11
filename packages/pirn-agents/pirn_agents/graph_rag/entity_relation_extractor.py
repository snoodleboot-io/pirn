"""``EntityRelationExtractor`` — schema-guided entity/relation extraction knot.

A :class:`Knot` that turns free text into typed graph elements at ingest time. It
follows the ``__init__`` → ``process`` contract with isinstance-validated inputs
and output:

    1. Build a schema-shaped extraction prompt from the text and the target
       :class:`~pirn_agents.graph_rag.extraction_schema.ExtractionSchema`.
    2. Decode it into a validated
       :class:`~pirn_agents.graph_rag.extraction_result.ExtractionResult` via the
       F20 :func:`structured_decode` path — provider-neutral, capability-gated
       native schema / forced-tool / constrained decoding with a retry fallback,
       so extraction works against any LLM provider.
    3. Reject any entity/relation whose type is outside the schema, or any
       relation that dangles off an unknown entity id.
    4. Map the typed result onto :class:`GraphNode` / :class:`GraphEdge` values
       and upsert them into any :class:`GraphStore` implementation.

The decoded :class:`ExtractionResult` is returned so callers can inspect or
re-use the typed extraction independently of the graph write.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.graph_rag.extraction_result import ExtractionResult
from pirn_agents.graph_rag.extraction_schema import ExtractionSchema
from pirn_agents.graph_stores.graph_edge import GraphEdge
from pirn_agents.graph_stores.graph_node import GraphNode
from pirn_agents.graph_stores.graph_store import GraphStore
from pirn_agents.specializations.structured_output.structured_decoder import structured_decode


class EntityRelationExtractor(Knot):
    """Extract typed entities/relations from text and upsert them into a graph."""

    def __init__(
        self,
        *,
        llm: Knot | LLMProvider,
        schema: Knot | ExtractionSchema,
        store: Knot | GraphStore,
        _config: KnotConfig,
        max_retries: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            llm=llm,
            schema=schema,
            store=store,
            max_retries=max_retries,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        text: str,
        llm: LLMProvider,
        schema: ExtractionSchema,
        store: GraphStore,
        max_retries: int = 3,
        **_: Any,
    ) -> ExtractionResult:
        """Extract entities/relations from ``text`` and upsert them into ``store``.

        Args:
            text: The source text to extract from.
            llm: The LLM provider used for schema-guided decoding.
            schema: The target entity/relation type vocabulary.
            store: The graph store the extracted elements are upserted into.
            max_retries: Retry budget for the structured-output fallback path.

        Returns:
            The validated :class:`ExtractionResult` (also written to ``store``).

        Raises:
            TypeError: If ``text``/``schema``/``store`` are the wrong type, or the
                decoded value is not an :class:`ExtractionResult`.
            ValueError: If ``text`` is blank, or an extracted entity/relation type
                is outside the schema, or a relation references an unknown entity.
        """
        if not isinstance(text, str):
            raise TypeError(
                f"EntityRelationExtractor: text must be a str, got {type(text).__name__}"
            )
        if not text.strip():
            raise ValueError("EntityRelationExtractor: text must be non-empty")
        if not isinstance(schema, ExtractionSchema):
            raise TypeError(
                f"EntityRelationExtractor: schema must be an ExtractionSchema, "
                f"got {type(schema).__name__}"
            )
        if not isinstance(store, GraphStore):
            raise TypeError(
                f"EntityRelationExtractor: store must be a GraphStore, got {type(store).__name__}"
            )
        prompt = self._build_prompt(text, schema)
        decoded = await structured_decode(
            prompt=prompt, llm=llm, model_class=ExtractionResult, max_retries=max_retries
        )
        if not isinstance(decoded, ExtractionResult):
            raise TypeError(
                f"EntityRelationExtractor: decoder returned {type(decoded).__name__}, "
                "expected ExtractionResult"
            )
        self._validate_against_schema(decoded, schema)
        nodes = [
            GraphNode.create(
                id=entity.id,
                type=entity.type,
                properties={"name": entity.name, **entity.properties},
            )
            for entity in decoded.entities
        ]
        edges = [
            GraphEdge.create(
                source_id=relation.source_id,
                target_id=relation.target_id,
                type=relation.type,
                properties=dict(relation.properties),
            )
            for relation in decoded.relations
        ]
        await store.upsert_nodes(nodes)
        await store.upsert_edges(edges)
        return decoded

    @staticmethod
    def _build_prompt(text: str, schema: ExtractionSchema) -> str:
        """Render the closed-vocabulary extraction prompt for ``text``."""
        entity_types = ", ".join(schema.entity_types)
        relation_types = ", ".join(schema.relation_types) or "(none)"
        return (
            "Extract the entities and relations from the text below.\n"
            f"Allowed entity types: {entity_types}.\n"
            f"Allowed relation types: {relation_types}.\n"
            "Give every entity a stable id and reference those ids from relations. "
            "Only use the allowed types.\n\n"
            f"Text:\n{text}"
        )

    @staticmethod
    def _validate_against_schema(result: ExtractionResult, schema: ExtractionSchema) -> None:
        """Reject out-of-schema types and relations that dangle off unknown ids."""
        allowed_entities = set(schema.entity_types)
        allowed_relations = set(schema.relation_types)
        entity_ids = {entity.id for entity in result.entities}
        for entity in result.entities:
            if entity.type not in allowed_entities:
                raise ValueError(
                    f"EntityRelationExtractor: entity {entity.id!r} has out-of-schema "
                    f"type {entity.type!r} (allowed: {sorted(allowed_entities)})"
                )
        for relation in result.relations:
            if relation.type not in allowed_relations:
                raise ValueError(
                    f"EntityRelationExtractor: relation has out-of-schema type "
                    f"{relation.type!r} (allowed: {sorted(allowed_relations)})"
                )
            if relation.source_id not in entity_ids or relation.target_id not in entity_ids:
                raise ValueError(
                    f"EntityRelationExtractor: relation {relation.type!r} references an "
                    f"unknown entity id ({relation.source_id!r} -> {relation.target_id!r})"
                )
