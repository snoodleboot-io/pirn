"""Tests for the :class:`EntityRelationExtractor` knot (S3, F20 structured output).

Uses the provider-neutral ``StubStructuredProvider`` (a capability-gated fake LLM
with a scripted response — no backend, no network) to drive the F20
``structured_decode`` path, and the zero-dep :class:`InMemoryGraphStore` to prove
extracted entities/relations upsert cleanly into any :class:`GraphStore`.
"""

from __future__ import annotations

import json
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.graph_rag.entity_relation_extractor import EntityRelationExtractor
from pirn_agents.graph_rag.extraction_result import ExtractionResult
from pirn_agents.graph_rag.extraction_schema import ExtractionSchema
from pirn_agents.graph_stores.in_memory_graph_store import InMemoryGraphStore
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from tests.specializations.structured_output.structured_stubs import (
    StubStructuredProvider,
    content_response,
)

_SCHEMA = ExtractionSchema.create(entity_types=["Person", "Company"], relation_types=["WORKS_AT"])


def _make_extractor() -> EntityRelationExtractor:
    with Tapestry():
        knot = EntityRelationExtractor.__new__(EntityRelationExtractor)
        object.__setattr__(knot, "_config", KnotConfig(id="extract"))
    return knot


def _provider(payload: object) -> StubStructuredProvider:
    """A native-schema provider returning ``payload`` as JSON content."""
    return StubStructuredProvider(
        capability=StructuredOutputCapability(native_schema=True),
        structured_response=content_response(json.dumps(payload)),
    )


_GOOD_PAYLOAD = {
    "entities": [
        {"id": "e1", "type": "Person", "name": "Ada", "properties": {"city": "London"}},
        {"id": "e2", "type": "Company", "name": "Acme", "properties": {}},
    ],
    "relations": [
        {"source_id": "e1", "target_id": "e2", "type": "WORKS_AT", "properties": {"since": 2020}}
    ],
}


class TestEntityRelationExtractor(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_and_upserts_into_graph_store(self) -> None:
        store = InMemoryGraphStore()
        extractor = _make_extractor()

        result = await extractor.process(
            text="Ada works at Acme.",
            llm=_provider(_GOOD_PAYLOAD),
            schema=_SCHEMA,
            store=store,
        )

        assert isinstance(result, ExtractionResult)
        assert {e.id for e in result.entities} == {"e1", "e2"}
        # Entities/relations upserted cleanly into the store.
        node = await store.get_node("e1")
        assert node is not None
        assert node.type == "Person"
        assert node.properties["name"] == "Ada"
        assert node.properties["city"] == "London"
        edge = await store.get_edge("e1|WORKS_AT|e2")
        assert edge is not None
        assert edge.properties["since"] == 2020

    async def test_rejects_out_of_schema_entity_type(self) -> None:
        store = InMemoryGraphStore()
        extractor = _make_extractor()
        payload = {
            "entities": [{"id": "e1", "type": "Alien", "name": "X", "properties": {}}],
            "relations": [],
        }
        with self.assertRaisesRegex(ValueError, "out-of-schema"):
            await extractor.process(text="t", llm=_provider(payload), schema=_SCHEMA, store=store)
        # Nothing partial should have leaked in before validation ran.
        assert await store.get_node("e1") is None

    async def test_rejects_out_of_schema_relation_type(self) -> None:
        store = InMemoryGraphStore()
        extractor = _make_extractor()
        payload = {
            "entities": [
                {"id": "e1", "type": "Person", "name": "A", "properties": {}},
                {"id": "e2", "type": "Company", "name": "B", "properties": {}},
            ],
            "relations": [
                {"source_id": "e1", "target_id": "e2", "type": "HATES", "properties": {}}
            ],
        }
        with self.assertRaisesRegex(ValueError, "out-of-schema"):
            await extractor.process(text="t", llm=_provider(payload), schema=_SCHEMA, store=store)

    async def test_rejects_dangling_relation(self) -> None:
        store = InMemoryGraphStore()
        extractor = _make_extractor()
        payload = {
            "entities": [{"id": "e1", "type": "Person", "name": "A", "properties": {}}],
            "relations": [
                {"source_id": "e1", "target_id": "ghost", "type": "WORKS_AT", "properties": {}}
            ],
        }
        with self.assertRaisesRegex(ValueError, "unknown entity id"):
            await extractor.process(text="t", llm=_provider(payload), schema=_SCHEMA, store=store)

    async def test_rejects_blank_text(self) -> None:
        extractor = _make_extractor()
        with self.assertRaisesRegex(ValueError, "text must be non-empty"):
            await extractor.process(
                text="   ", llm=_provider(_GOOD_PAYLOAD), schema=_SCHEMA, store=InMemoryGraphStore()
            )

    async def test_rejects_bad_schema_type(self) -> None:
        extractor = _make_extractor()
        with self.assertRaisesRegex(TypeError, "schema must be an ExtractionSchema"):
            await extractor.process(
                text="t",
                llm=_provider(_GOOD_PAYLOAD),
                schema="nope",  # type: ignore[arg-type]
                store=InMemoryGraphStore(),
            )

    async def test_rejects_bad_store_type(self) -> None:
        extractor = _make_extractor()
        with self.assertRaisesRegex(TypeError, "store must be a GraphStore"):
            await extractor.process(
                text="t",
                llm=_provider(_GOOD_PAYLOAD),
                schema=_SCHEMA,
                store="nope",  # type: ignore[arg-type]
            )

    async def test_malformed_llm_output_surfaces_error(self) -> None:
        # Native content is not valid JSON and the fallback chat also fails, so
        # the F20 decode path exhausts and raises rather than silently passing.
        store = InMemoryGraphStore()
        extractor = _make_extractor()
        provider = StubStructuredProvider(
            capability=StructuredOutputCapability(native_schema=True),
            structured_response=content_response("this is not json"),
            chat_responses=("still not json",),
        )
        with self.assertRaises(ValueError):
            await extractor.process(
                text="t", llm=provider, schema=_SCHEMA, store=store, max_retries=1
            )


if __name__ == "__main__":
    unittest.main()
