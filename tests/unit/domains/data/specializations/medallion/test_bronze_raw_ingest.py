"""Tests for :class:`BronzeRawIngest`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.specializations.medallion.bronze_raw_ingest import (
    BronzeRawIngest,
)


def _make_pool() -> MagicMock:
    return MagicMock(spec=DatabaseConnectionPool)


class TestBronzeRawIngestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        ingest = BronzeRawIngest(
            source_pool=_make_pool(),
            source_query="SELECT id, name FROM customers",
            target_pool=_make_pool(),
            target_table="bronze_customers",
            source_columns=["id", "name"],
            source_uri="db://src/customers",
            _config=KnotConfig(id="bronze"),
        )
        self.assertIsInstance(ingest, BronzeRawIngest)

    def test_rejects_non_pool_source(self) -> None:
        with self.assertRaises(TypeError):
            BronzeRawIngest(
                source_pool="not-pool",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="bronze_customers",
                source_columns=["id"],
                source_uri="db://src",
                _config=KnotConfig(id="bronze"),
            )

    def test_rejects_non_pool_target(self) -> None:
        with self.assertRaises(TypeError):
            BronzeRawIngest(
                source_pool=_make_pool(),
                source_query="SELECT 1",
                target_pool="not-pool",  # type: ignore[arg-type]
                target_table="bronze_customers",
                source_columns=["id"],
                source_uri="db://src",
                _config=KnotConfig(id="bronze"),
            )

    def test_rejects_empty_source_query(self) -> None:
        with self.assertRaises(ValueError):
            BronzeRawIngest(
                source_pool=_make_pool(),
                source_query="",
                target_pool=_make_pool(),
                target_table="bronze_customers",
                source_columns=["id"],
                source_uri="db://src",
                _config=KnotConfig(id="bronze"),
            )

    def test_rejects_empty_source_columns(self) -> None:
        with self.assertRaises(ValueError):
            BronzeRawIngest(
                source_pool=_make_pool(),
                source_query="SELECT 1",
                target_pool=_make_pool(),
                target_table="bronze_customers",
                source_columns=[],
                source_uri="db://src",
                _config=KnotConfig(id="bronze"),
            )

    def test_insert_query_includes_metadata_columns(self) -> None:
        ingest = BronzeRawIngest(
            source_pool=_make_pool(),
            source_query="SELECT id FROM t",
            target_pool=_make_pool(),
            target_table="bronze_t",
            source_columns=["id"],
            source_uri="db://src/t",
            _config=KnotConfig(id="bronze"),
        )
        q = ingest.insert_query
        self.assertIn("_ingested_at", q)
        self.assertIn("_source_uri", q)
        self.assertIn("bronze_t", q)
