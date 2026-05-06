"""Tests for :class:`pirn.domains.connectors.object_storage.hdfs_config.HDFSConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.object_storage.hdfs_config import HDFSConfig


class TestHDFSConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = HDFSConfig()
        self.assertEqual(cfg.namenode_host, "localhost")
        self.assertEqual(cfg.namenode_port, 50070)
        self.assertEqual(cfg.user, "")
        self.assertEqual(cfg.base_path, "/")
        self.assertTrue(cfg.use_webhdfs)
        self.assertEqual(cfg.chunk_size, 1 << 20)

    def test_construct_with_fields(self) -> None:
        cfg = HDFSConfig(
            namenode_host="hdfs-namenode.example.com",
            namenode_port=8020,
            user="hadoop",
            base_path="/data",
            use_webhdfs=False,
            chunk_size=2 << 20,
        )
        self.assertEqual(cfg.namenode_host, "hdfs-namenode.example.com")
        self.assertEqual(cfg.namenode_port, 8020)
        self.assertFalse(cfg.use_webhdfs)
        self.assertEqual(cfg.base_path, "/data")

    def test_no_sensitive_fields(self) -> None:
        self.assertEqual(HDFSConfig.sensitive_fields, ())

    def test_frozen(self) -> None:
        cfg = HDFSConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.namenode_host = "mutated"  # type: ignore[misc]
