"""Tests for :class:`pirn.domains.connectors.databases.snowflake_config.SnowflakeConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.databases.snowflake_config import SnowflakeConfig


class TestSnowflakeConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = SnowflakeConfig()
        self.assertIsNone(cfg.account)
        self.assertIsNone(cfg.user)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.warehouse)
        self.assertIsNone(cfg.database)
        self.assertIsNone(cfg.schema)
        self.assertIsNone(cfg.role)

    def test_construct_with_fields(self) -> None:
        cfg = SnowflakeConfig(
            account="xy12345.us-east-1",
            user="sf_user",
            password="sf-pw",
            warehouse="COMPUTE_WH",
            database="ANALYTICS",
            schema="PUBLIC",
            role="ANALYST",
        )
        self.assertEqual(cfg.account, "xy12345.us-east-1")
        self.assertEqual(cfg.warehouse, "COMPUTE_WH")
        self.assertEqual(cfg.role, "ANALYST")

    def test_repr_redacts_password(self) -> None:
        cfg = SnowflakeConfig(password="sf-secret")
        text = repr(cfg)
        self.assertNotIn("sf-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = SnowflakeConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.account = "mutated"  # type: ignore[misc]
