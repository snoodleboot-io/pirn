"""Tests for :class:`pirn.domains.connectors.object_storage.gcs_config.GCSConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.object_storage.gcs_config import GCSConfig


class TestGCSConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = GCSConfig()
        self.assertIsNone(cfg.bucket)
        self.assertIsNone(cfg.service_account_json)
        self.assertIsNone(cfg.project)
        self.assertEqual(cfg.chunk_size, 65536)

    def test_construct_with_fields(self) -> None:
        cfg = GCSConfig(
            bucket="my-bucket",
            service_account_json="/keys/sa.json",
            project="my-project",
            chunk_size=131072,
        )
        self.assertEqual(cfg.bucket, "my-bucket")
        self.assertEqual(cfg.project, "my-project")
        self.assertEqual(cfg.chunk_size, 131072)

    def test_sensitive_fields(self) -> None:
        self.assertIn("service_account_json", GCSConfig.sensitive_fields)

    def test_repr_redacts_service_account_json(self) -> None:
        cfg = GCSConfig(service_account_json="/path/to/secret.json")
        text = repr(cfg)
        self.assertNotIn("/path/to/secret.json", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = GCSConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.bucket = "mutated"  # type: ignore[misc]
