"""Tests for :class:`pirn.domains.connectors.document.firestore_config.FirestoreConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.document.firestore_config import FirestoreConfig


class TestFirestoreConfig(unittest.TestCase):
    def test_construct_with_project(self) -> None:
        cfg = FirestoreConfig(project_id="my-gcp-project")
        self.assertEqual(cfg.project_id, "my-gcp-project")
        self.assertIsNone(cfg.credentials_json)
        self.assertEqual(cfg.database_id, "(default)")
        self.assertEqual(cfg.collection, "")

    def test_empty_project_raises(self) -> None:
        with self.assertRaises(ValueError):
            FirestoreConfig(project_id="")

    def test_construct_with_all_fields(self) -> None:
        cfg = FirestoreConfig(
            project_id="my-project",
            credentials_json='{"type": "service_account"}',
            database_id="mydb",
            collection="my_collection",
        )
        self.assertEqual(cfg.database_id, "mydb")
        self.assertEqual(cfg.collection, "my_collection")

    def test_sensitive_fields(self) -> None:
        self.assertIn("credentials_json", FirestoreConfig.sensitive_fields)

    def test_repr_redacts_credentials_json(self) -> None:
        cfg = FirestoreConfig(
            project_id="proj",
            credentials_json='{"private_key": "secret"}',
        )
        text = repr(cfg)
        self.assertNotIn("secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = FirestoreConfig(project_id="proj")
        with self.assertRaises((AttributeError, TypeError)):
            cfg.project_id = "mutated"  # type: ignore[misc]
