"""Security tests: M-4 — LocalDiskDataStore path traversal guard."""

from __future__ import annotations

import os
import tempfile
import unittest


class TestLocalDiskDataStorePathTraversal(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        os.environ["PIRN_ENV"] = "test"
        from pirn.backends._signer import _Signer
        self._signer = _Signer.test_signer()

    def tearDown(self) -> None:
        os.environ.pop("PIRN_ENV", None)

    def test_normal_sha256_hash_accepted(self) -> None:
        from pirn.backends.disk import LocalDiskDataStore
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalDiskDataStore(tmp, signer=self._signer)
            key = store._object_key("sha256:" + "a" * 64)
            assert tmp in key

    def test_path_traversal_via_content_hash_rejected(self) -> None:
        from pirn.backends.disk import LocalDiskDataStore
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalDiskDataStore(tmp, signer=self._signer)
            with self.assertRaises(ValueError) as ctx:
                store._object_key("sha256:../../../etc/passwd")
            assert "outside the store root" in str(ctx.exception)

    def test_absolute_path_in_hash_rejected(self) -> None:
        from pirn.backends.disk import LocalDiskDataStore
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalDiskDataStore(tmp, signer=self._signer)
            with self.assertRaises(ValueError):
                store._object_key("/etc/shadow")

    def test_null_byte_in_hash_rejected(self) -> None:
        from pirn.backends.disk import LocalDiskDataStore
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalDiskDataStore(tmp, signer=self._signer)
            with self.assertRaises((ValueError, Exception)):
                store._object_key("sha256:\x00../../evil")
