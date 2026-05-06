"""Tests for :class:`pirn.domains.connectors.object_storage.local_filesystem_config.LocalFilesystemConfig`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pirn.domains.connectors.object_storage.local_filesystem_config import LocalFilesystemConfig


class TestLocalFilesystemConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = LocalFilesystemConfig()
        self.assertEqual(cfg.root, Path())
        self.assertEqual(cfg.chunk_size, 1 << 20)
        self.assertTrue(cfg.create_root)

    def test_construct_with_fields(self) -> None:
        cfg = LocalFilesystemConfig(
            root=Path("/data/store"),
            chunk_size=65536,
            create_root=False,
        )
        self.assertEqual(cfg.root, Path("/data/store"))
        self.assertEqual(cfg.chunk_size, 65536)
        self.assertFalse(cfg.create_root)

    def test_no_sensitive_fields(self) -> None:
        self.assertEqual(LocalFilesystemConfig.sensitive_fields, ())

    def test_frozen(self) -> None:
        cfg = LocalFilesystemConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.root = Path("/mutated")  # type: ignore[misc]

    def test_root_defaults_to_empty_path(self) -> None:
        cfg1 = LocalFilesystemConfig()
        cfg2 = LocalFilesystemConfig()
        self.assertEqual(cfg1.root, Path())
        self.assertEqual(cfg2.root, Path())
