"""Security tests: H-2 — allow_unsigned=True requires PIRN_ALLOW_UNSIGNED=1."""

from __future__ import annotations

import os
import tempfile
import unittest


class TestCloudObjectStoreUnsignedGate(unittest.TestCase):
    def test_unsigned_without_env_var_raises(self) -> None:
        os.environ.pop("PIRN_ALLOW_UNSIGNED", None)
        from pirn.backends.disk import LocalDiskDataStore
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                LocalDiskDataStore(tmp, allow_unsigned=True)
            assert "PIRN_ALLOW_UNSIGNED" in str(ctx.exception)

    def test_unsigned_with_env_var_emits_warning(self) -> None:
        os.environ["PIRN_ALLOW_UNSIGNED"] = "1"
        import importlib
        import pirn.backends.base._cloud_object_store as mod
        importlib.reload(mod)
        import pirn.backends.disk as disk_mod
        importlib.reload(disk_mod)
        from pirn.backends.disk import LocalDiskDataStore
        import logging
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertLogs("pirn.backends.base._cloud_object_store", level="WARNING") as cm:
                    LocalDiskDataStore(tmp, allow_unsigned=True)
                assert any("allow_unsigned" in line for line in cm.output)
        finally:
            os.environ.pop("PIRN_ALLOW_UNSIGNED", None)

    def test_signed_store_requires_no_env_var(self) -> None:
        os.environ.pop("PIRN_ALLOW_UNSIGNED", None)
        from pirn.backends._signer import _Signer
        from pirn.backends.disk import LocalDiskDataStore
        os.environ["PIRN_ENV"] = "test"
        try:
            signer = _Signer.test_signer()
            with tempfile.TemporaryDirectory() as tmp:
                store = LocalDiskDataStore(tmp, signer=signer)
                assert store is not None
        finally:
            os.environ.pop("PIRN_ENV", None)


class TestValKeyDataStoreUnsignedGate(unittest.TestCase):
    def test_unsigned_without_env_var_raises(self) -> None:
        os.environ.pop("PIRN_ALLOW_UNSIGNED", None)
        from pirn.backends.valkey.valkey_data_store import ValKeyDataStore
        with self.assertRaises(ValueError) as ctx:
            ValKeyDataStore(allow_unsigned=True)
        assert "PIRN_ALLOW_UNSIGNED" in str(ctx.exception)
