"""Tests for :class:`StampBronzeMetadataKnot`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specializations.medallion.stamp_bronze_metadata_knot import (
    StampBronzeMetadataKnot,
)


class TestStampBronzeMetadataKnotConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        knot = StampBronzeMetadataKnot(
            rows=MagicMock(),
            source_uri="db://src/table",
            _config=KnotConfig(id="stamp"),
        )
        self.assertIsInstance(knot, StampBronzeMetadataKnot)

    def test_rejects_empty_source_uri(self) -> None:
        with self.assertRaises(ValueError):
            StampBronzeMetadataKnot(
                rows=MagicMock(),
                source_uri="",
                _config=KnotConfig(id="stamp"),
            )

    def test_rejects_non_string_source_uri(self) -> None:
        with self.assertRaises(ValueError):
            StampBronzeMetadataKnot(
                rows=MagicMock(),
                source_uri=None,  # type: ignore[arg-type]
                _config=KnotConfig(id="stamp"),
            )


class TestStampBronzeMetadataKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_metadata_to_each_row(self) -> None:
        knot = StampBronzeMetadataKnot(
            rows=MagicMock(),
            source_uri="db://src/orders",
            _config=KnotConfig(id="stamp"),
        )
        rows = [(1, "alice"), (2, "bob")]
        result = await knot.process(rows=rows, **{})
        self.assertEqual(len(result), 2)
        for stamped in result:
            self.assertEqual(len(stamped), 4)  # 2 original + ingested_at + source_uri
            self.assertEqual(stamped[-1], "db://src/orders")

    async def test_ingested_at_is_iso_string(self) -> None:
        knot = StampBronzeMetadataKnot(
            rows=MagicMock(),
            source_uri="db://src/orders",
            _config=KnotConfig(id="stamp"),
        )
        result = await knot.process(rows=[(42,)], **{})
        ingested_at = result[0][-2]
        self.assertIsInstance(ingested_at, str)
        self.assertIn("T", ingested_at)

    async def test_empty_rows_returns_empty_list(self) -> None:
        knot = StampBronzeMetadataKnot(
            rows=MagicMock(),
            source_uri="db://src/orders",
            _config=KnotConfig(id="stamp"),
        )
        result = await knot.process(rows=[], **{})
        self.assertEqual(result, [])
