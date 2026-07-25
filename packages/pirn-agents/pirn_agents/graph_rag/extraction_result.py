"""``ExtractionResult`` — the typed entity/relation payload of one extraction.

The top-level pydantic model the F20 structured-output path decodes for the
:class:`~pirn_agents.graph_rag.entity_relation_extractor.EntityRelationExtractor`.
It is the ``model_class`` handed to ``structured_decode``, so the LLM's output is
validated into typed :class:`ExtractedEntity` / :class:`ExtractedRelation` lists
before the extractor maps them onto graph nodes and edges.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pirn_agents.graph_rag.extracted_entity import ExtractedEntity
from pirn_agents.graph_rag.extracted_relation import ExtractedRelation


class ExtractionResult(BaseModel):
    """The entities and relations extracted from a single piece of text.

    Attributes
    ----------
    entities:
        The typed entities extracted from the text.
    relations:
        The typed relations extracted between those entities.
    """

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
