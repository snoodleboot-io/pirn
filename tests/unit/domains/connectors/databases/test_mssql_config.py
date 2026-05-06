"""Tests for :class:`pirn.domains.connectors.databases.mssql_config.MssqlConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.databases.mssql_config import MssqlConfig


class TestMssqlConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = MssqlConfig()
        self.assertIsNone(cfg.dsn)
        self.assertIsNone(cfg.host)
        self.assertEqual(cfg.port, 1433)
        self.assertIsNone(cfg.user)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.database)
        self.assertEqual(cfg.driver, "ODBC Driver 18 for SQL Server")
        self.assertEqual(cfg.min_size, 1)
        self.assertEqual(cfg.max_size, 10)
        self.assertTrue(cfg.autocommit)

    def test_build_dsn_from_explicit_dsn(self) -> None:
        cfg = MssqlConfig(dsn="DRIVER={ODBC Driver 18 for SQL Server};SERVER=db,1433;")
        result = cfg.build_dsn()
        self.assertEqual(result, "DRIVER={ODBC Driver 18 for SQL Server};SERVER=db,1433;")

    def test_build_dsn_constructs_from_parts(self) -> None:
        cfg = MssqlConfig(host="sqlserver", port=1433, database="mydb", user="sa", password="pw")
        dsn = cfg.build_dsn()
        self.assertIn("SERVER=sqlserver,1433", dsn)
        self.assertIn("DATABASE=mydb", dsn)
        self.assertIn("UID=sa", dsn)
        self.assertIn("PWD=pw", dsn)

    def test_build_dsn_no_host(self) -> None:
        cfg = MssqlConfig(database="mydb")
        dsn = cfg.build_dsn()
        self.assertIn("DATABASE=mydb", dsn)
        self.assertNotIn("SERVER=", dsn)

    def test_repr_redacts_password(self) -> None:
        cfg = MssqlConfig(password="mssql-secret")
        text = repr(cfg)
        self.assertNotIn("mssql-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = MssqlConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host = "mutated"  # type: ignore[misc]
