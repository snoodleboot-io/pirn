"""Tests for :class:`WatermarkIncrementalExtract`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.ingestion.watermark_incremental_extract import (
    WatermarkIncrementalExtract,
)


def _make_pool() -> MagicMock:
    pool = MagicMock(spec=DatabaseConnectionPool)
    return pool


class TestWatermarkIncrementalExtractConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        src = _make_pool()
        tgt = _make_pool()
        ext = WatermarkIncrementalExtract(
            source_pool=src,
            source_table="events",
            columns=["id", "loaded_at"],
            target_pool=tgt,
            target_table="events_copy",
            watermark_column="loaded_at",
            _config=KnotConfig(id="wie"),
        )
        self.assertIsInstance(ext, WatermarkIncrementalExtract)

    def test_rejects_non_pool_source(self) -> None:
        tgt = _make_pool()
        with self.assertRaises(TypeError):
            WatermarkIncrementalExtract(
                source_pool="not-pool",  # type: ignore[arg-type]
                source_table="events",
                columns=["id"],
                target_pool=tgt,
                target_table="events_copy",
                watermark_column="loaded_at",
                _config=KnotConfig(id="wie"),
            )

    def test_rejects_non_pool_target(self) -> None:
        src = _make_pool()
        with self.assertRaises(TypeError):
            WatermarkIncrementalExtract(
                source_pool=src,
                source_table="events",
                columns=["id"],
                target_pool="not-pool",  # type: ignore[arg-type]
                target_table="events_copy",
                watermark_column="loaded_at",
                _config=KnotConfig(id="wie"),
            )

    def test_rejects_empty_columns(self) -> None:
        src = _make_pool()
        tgt = _make_pool()
        with self.assertRaises(ValueError):
            WatermarkIncrementalExtract(
                source_pool=src,
                source_table="events",
                columns=[],
                target_pool=tgt,
                target_table="events_copy",
                watermark_column="loaded_at",
                _config=KnotConfig(id="wie"),
            )

    def test_rejects_empty_source_table(self) -> None:
        src = _make_pool()
        tgt = _make_pool()
        with self.assertRaises(ValueError):
            WatermarkIncrementalExtract(
                source_pool=src,
                source_table="",
                columns=["id"],
                target_pool=tgt,
                target_table="events_copy",
                watermark_column="loaded_at",
                _config=KnotConfig(id="wie"),
            )

    def test_insert_query_contains_target_table(self) -> None:
        src = _make_pool()
        tgt = _make_pool()
        ext = WatermarkIncrementalExtract(
            source_pool=src,
            source_table="events",
            columns=["id", "loaded_at"],
            target_pool=tgt,
            target_table="events_copy",
            watermark_column="loaded_at",
            _config=KnotConfig(id="wie"),
        )
        self.assertIn("events_copy", ext._insert_query)
        self.assertIn("INSERT INTO", ext._insert_query)
