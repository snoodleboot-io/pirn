"""``ExtractionSchema`` — the target entity/relation types guiding extraction.

A frozen, hashable value naming the entity and relation types the
:class:`~pirn_agents.graph_rag.entity_relation_extractor.EntityRelationExtractor`
is allowed to emit. It shapes the extraction prompt (so the LLM knows the closed
vocabulary) and is used to validate the decoded
:class:`~pirn_agents.graph_rag.extraction_result.ExtractionResult`, rejecting any
out-of-schema entity or relation type.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionSchema:
    """The closed set of entity / relation types extraction may produce.

    Attributes
    ----------
    entity_types:
        The allowed entity types (e.g. ``("Person", "Company")``).
    relation_types:
        The allowed relation types (e.g. ``("WORKS_AT",)``).
    """

    entity_types: tuple[str, ...]
    relation_types: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        entity_types: Sequence[str],
        relation_types: Sequence[str],
    ) -> ExtractionSchema:
        """Build a schema from any string sequences, normalising to tuples.

        Args:
            entity_types: The allowed entity types; must be a non-empty sequence
                of non-empty strings.
            relation_types: The allowed relation types; each must be a non-empty
                string (an empty sequence means "entities only").

        Returns:
            A frozen :class:`ExtractionSchema`.

        Raises:
            ValueError: If ``entity_types`` is empty or any type is not a
                non-empty string.
        """
        entities = tuple(entity_types)
        relations = tuple(relation_types)
        if not entities:
            raise ValueError("ExtractionSchema: entity_types must be non-empty")
        for value in (*entities, *relations):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ExtractionSchema: every type must be a non-empty str, got {value!r}"
                )
        return cls(entity_types=entities, relation_types=relations)
