"""Tests for :func:`connection_config` decorator."""

from __future__ import annotations

import dataclasses
import unittest

from pirn.connectors.connection_config_decorator import connection_config


class TestConnectionConfigDecorator(unittest.TestCase):
    def test_applied_directly_to_class(self) -> None:
        @connection_config
        class MyConfig:
            host: str = "localhost"
            port: int = 5432

        cfg = MyConfig()
        self.assertEqual(cfg.host, "localhost")
        self.assertEqual(cfg.port, 5432)

    def test_frozen_by_default(self) -> None:
        @connection_config
        class MyConfig:
            host: str = "localhost"

        cfg = MyConfig()
        with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError)):
            cfg.host = "other"  # type: ignore[misc]

    def test_repr_not_generated(self) -> None:
        @connection_config
        class MyConfig:
            host: str = "localhost"

        # Should not have a freshly-generated repr in its own __dict__
        self.assertNotIn("__repr__", MyConfig.__dict__)

    def test_applied_with_kwargs(self) -> None:
        @connection_config(frozen=False)
        class MutableConfig:
            host: str = "localhost"

        cfg = MutableConfig()
        cfg.host = "changed"
        self.assertEqual(cfg.host, "changed")

    def test_is_dataclass(self) -> None:
        @connection_config
        class MyConfig:
            timeout: int = 30

        self.assertTrue(dataclasses.is_dataclass(MyConfig))
