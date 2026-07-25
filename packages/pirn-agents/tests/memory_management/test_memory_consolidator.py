"""Unit tests for :class:`MemoryConsolidator`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.memory_management.memory_consolidator import MemoryConsolidator
from tests.memory_management.conftest import (
    RecordingMemoryStore,
    StubSummarizer,
    make_record,
)


def _make_knot() -> MemoryConsolidator:
    with Tapestry():
        return MemoryConsolidator(
            records=[],
            summarizer=StubSummarizer(),
            _config=KnotConfig(id="mc"),
        )


class TestMemoryConsolidator(unittest.IsolatedAsyncioTestCase):
    async def test_merges_near_duplicates_into_one_semantic_record(self) -> None:
        knot = _make_knot()
        summarizer = StubSummarizer()
        records = [
            make_record(id="e1", content="the sky is blue today"),
            make_record(id="e2", content="the sky is blue now"),
        ]
        result = await knot.process(records=records, summarizer=summarizer)
        assert len(result) == 1
        assert result[0].kind == "semantic"
        assert result[0].content.startswith("SUMMARY(")
        assert summarizer.calls  # F17 summarizer seam was invoked

    async def test_derivation_records_source_ids(self) -> None:
        knot = _make_knot()
        records = [
            make_record(id="e1", content="alpha beta gamma delta"),
            make_record(id="e2", content="alpha beta gamma delta"),
        ]
        result = await knot.process(records=records, summarizer=StubSummarizer())
        derivation = result[0].provenance.derivation
        assert derivation is not None
        assert "e1" in derivation and "e2" in derivation
        assert result[0].metadata["merged_count"] == 2

    async def test_no_op_on_already_clean_data(self) -> None:
        knot = _make_knot()
        records = [
            make_record(id="e1", content="apples and oranges grow"),
            make_record(id="e2", content="rockets fly to the moon"),
        ]
        result = await knot.process(records=records, summarizer=StubSummarizer())
        assert result == []

    async def test_ignores_non_episodic_records(self) -> None:
        knot = _make_knot()
        records = [
            make_record(id="s1", kind="semantic", content="duplicate content here"),
            make_record(id="s2", kind="semantic", content="duplicate content here"),
        ]
        result = await knot.process(records=records, summarizer=StubSummarizer())
        assert result == []

    async def test_persists_to_store_when_supplied(self) -> None:
        knot = _make_knot()
        store = RecordingMemoryStore()
        records = [
            make_record(id="e1", content="shared token phrase here"),
            make_record(id="e2", content="shared token phrase here"),
        ]
        result = await knot.process(records=records, summarizer=StubSummarizer(), store=store)
        assert result[0].id in store.data

    async def test_conflict_winner_seeds_provenance_timestamp(self) -> None:
        knot = _make_knot()
        newer = datetime(2026, 9, 1, tzinfo=UTC)
        records = [
            make_record(
                id="e1",
                content="same words repeated often",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            make_record(id="e2", content="same words repeated often", timestamp=newer),
        ]
        result = await knot.process(records=records, summarizer=StubSummarizer())
        assert result[0].provenance.timestamp == newer

    async def test_deterministic_id_for_same_group(self) -> None:
        knot = _make_knot()
        records = [
            make_record(id="e1", content="stable identity content block"),
            make_record(id="e2", content="stable identity content block"),
        ]
        first = await knot.process(records=records, summarizer=StubSummarizer())
        second = await knot.process(records=records, summarizer=StubSummarizer())
        assert first[0].id == second[0].id

    async def test_rejects_non_summarizer(self) -> None:
        knot = _make_knot()
        with self.assertRaises(TypeError):
            await knot.process(records=[], summarizer="bad")  # type: ignore[arg-type]
