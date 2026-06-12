"""Tests for :class:`pirn.connectors.databases.bigquery_config.BigqueryConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.databases.bigquery_config import BigqueryConfig


class TestBigqueryConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = BigqueryConfig()
        self.assertIsNone(cfg.project_id)
        self.assertIsNone(cfg.dataset_id)
        self.assertIsNone(cfg.credentials_path)
        self.assertEqual(cfg.location, "US")

    def test_construct_with_fields(self) -> None:
        cfg = BigqueryConfig(
            project_id="my-project",
            dataset_id="my_dataset",
            credentials_path="/keys/sa.json",
            location="EU",
        )
        self.assertEqual(cfg.project_id, "my-project")
        self.assertEqual(cfg.dataset_id, "my_dataset")
        self.assertEqual(cfg.credentials_path, "/keys/sa.json")
        self.assertEqual(cfg.location, "EU")

    def test_sensitive_fields(self) -> None:
        self.assertIn("credentials_path", BigqueryConfig.sensitive_fields)

    def test_repr_redacts_credentials_path(self) -> None:
        cfg = BigqueryConfig(credentials_path="/keys/sa.json")
        text = repr(cfg)
        self.assertNotIn("/keys/sa.json", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = BigqueryConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.project_id = "mutated"  # type: ignore[misc]

    def test_audit_dict(self) -> None:
        cfg = BigqueryConfig(project_id="proj", credentials_path="/k.json")
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["credentials_path"], "<redacted>")
        self.assertEqual(audit["project_id"], "proj")
