"""Tests for :class:`pirn.connectors.timeseries.influxdb_config.InfluxDBConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.timeseries.influxdb_config import InfluxDBConfig


class TestInfluxDBConfig(unittest.TestCase):
    def test_construct_with_required_fields(self) -> None:
        cfg = InfluxDBConfig(org="my-org", bucket="my-bucket")
        self.assertEqual(cfg.org, "my-org")
        self.assertEqual(cfg.bucket, "my-bucket")
        self.assertEqual(cfg.url, "http://localhost:8086")
        self.assertEqual(cfg.token, "")
        self.assertEqual(cfg.timeout, 10_000)
        self.assertTrue(cfg.verify_ssl)

    def test_empty_org_raises(self) -> None:
        with self.assertRaises(ValueError):
            InfluxDBConfig(org="", bucket="b")

    def test_empty_bucket_raises(self) -> None:
        with self.assertRaises(ValueError):
            InfluxDBConfig(org="o", bucket="")

    def test_construct_with_all_fields(self) -> None:
        cfg = InfluxDBConfig(
            url="https://influxdb.example.com",
            token="influx-token",
            org="myorg",
            bucket="mybucket",
            timeout=30_000,
            verify_ssl=False,
        )
        self.assertEqual(cfg.url, "https://influxdb.example.com")
        self.assertFalse(cfg.verify_ssl)

    def test_sensitive_fields(self) -> None:
        self.assertIn("token", InfluxDBConfig.sensitive_fields)

    def test_repr_redacts_token(self) -> None:
        cfg = InfluxDBConfig(token="influx-secret", org="o", bucket="b")
        text = repr(cfg)
        self.assertNotIn("influx-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = InfluxDBConfig(org="o", bucket="b")
        with self.assertRaises((AttributeError, TypeError)):
            cfg.url = "mutated"  # type: ignore[misc]
