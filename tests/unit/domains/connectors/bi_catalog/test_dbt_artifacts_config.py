"""Tests for :class:`pirn.connectors.bi_catalog.dbt_artifacts_config.DbtArtifactsConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.bi_catalog.dbt_artifacts_config import DbtArtifactsConfig


class TestDbtArtifactsConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = DbtArtifactsConfig()
        self.assertIsNone(cfg.target_path)

    def test_construct_with_path(self) -> None:
        cfg = DbtArtifactsConfig(target_path="/project/target")
        self.assertEqual(cfg.target_path, "/project/target")

    def test_no_sensitive_fields(self) -> None:
        self.assertEqual(DbtArtifactsConfig.sensitive_fields, ())

    def test_repr_shows_path(self) -> None:
        cfg = DbtArtifactsConfig(target_path="/project/target")
        self.assertIn("/project/target", repr(cfg))

    def test_frozen(self) -> None:
        cfg = DbtArtifactsConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.target_path = "mutated"  # type: ignore[misc]

    def test_audit_dict_class_marker(self) -> None:
        cfg = DbtArtifactsConfig()
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["_class"], "DbtArtifactsConfig")
