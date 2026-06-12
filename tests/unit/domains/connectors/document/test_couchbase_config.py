"""Tests for :class:`pirn.connectors.document.couchbase_config.CouchbaseConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.document.couchbase_config import CouchbaseConfig


class TestCouchbaseConfig(unittest.TestCase):
    def test_construct_with_bucket(self) -> None:
        cfg = CouchbaseConfig(bucket="my-bucket", username="admin", password="pw")
        self.assertEqual(cfg.bucket, "my-bucket")
        self.assertEqual(cfg.connection_string, "couchbase://localhost")

    def test_defaults(self) -> None:
        cfg = CouchbaseConfig(bucket="b")
        self.assertEqual(cfg.scope, "_default")
        self.assertEqual(cfg.collection, "_default")
        self.assertEqual(cfg.kv_timeout_ms, 2500)
        self.assertEqual(cfg.query_timeout_ms, 75000)

    def test_empty_bucket_raises(self) -> None:
        with self.assertRaises(ValueError):
            CouchbaseConfig(bucket="")

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", CouchbaseConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = CouchbaseConfig(bucket="b", password="cb-secret")
        text = repr(cfg)
        self.assertNotIn("cb-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = CouchbaseConfig(bucket="b")
        with self.assertRaises((AttributeError, TypeError)):
            cfg.bucket = "mutated"  # type: ignore[misc]
