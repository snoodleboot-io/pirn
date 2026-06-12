"""Tests for :class:`BigqueryStubJobConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.databases._bigquery_stub_job_config import (
    BigqueryStubJobConfig,
)


class TestBigqueryStubJobConfig(unittest.TestCase):
    def test_construction_stores_query_parameters(self) -> None:
        params = [("name", "STRING", "Alice")]
        cfg = BigqueryStubJobConfig(query_parameters=params)
        self.assertEqual(cfg.query_parameters, params)

    def test_empty_parameters(self) -> None:
        cfg = BigqueryStubJobConfig(query_parameters=[])
        self.assertEqual(cfg.query_parameters, [])

    def test_mutable_attribute(self) -> None:
        params = [1, 2, 3]
        cfg = BigqueryStubJobConfig(query_parameters=params)
        cfg.query_parameters.append(4)
        self.assertEqual(cfg.query_parameters, [1, 2, 3, 4])
