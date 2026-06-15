"""Tests for HMAC signing on DataStore backends (findings C-1 and I-14)."""

from __future__ import annotations

import base64
import unittest
import unittest.mock
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pirn.backends._signer import _Signer
from pirn.backends.disk import LocalDiskDataStore

_KEY = b"test-signing-key-32-bytes-abcdefg"[:32]
_SIGNER = _Signer(_KEY)


# ------------------------------------------------------------------ _Signer



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    def test_sign_verify_round_trip(self) -> None:
        payload = b"hello world"
        signed = _SIGNER.sign(payload)
        assert _SIGNER.verify(signed) == payload
    
    
    def test_verify_too_short_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "too short"):
            _SIGNER.verify(b"\x00" * 10)
    
    
    def test_verify_tampered_raises(self) -> None:
        signed = _SIGNER.sign(b"data")
        tampered = bytearray(signed)
        tampered[-1] ^= 0xFF
        with self.assertRaisesRegex(ValueError, "HMAC signature mismatch"):
            _SIGNER.verify(bytes(tampered))
    
    
    def test_signer_from_env_reads_base64(self) -> None:
        key = b"exactly-32-bytes-for-hmac-sha256"
        with unittest.mock.patch.dict(__import__("os").environ, {"PIRN_SIGNING_KEY": base64.b64encode(key).decode()}):
            signer = _Signer.from_env()
            assert signer.sign(b"x") != b"x"

    def test_signer_from_env_custom_var(self) -> None:
        key = b"exactly-32-bytes-for-hmac-sha256"
        with unittest.mock.patch.dict(__import__("os").environ, {"MY_CUSTOM_KEY": base64.b64encode(key).decode()}):
            signer = _Signer.from_env("MY_CUSTOM_KEY")
            assert signer.sign(b"x") != b"x"
    
    
    def test_signer_from_env_missing_raises(self) -> None:
        with unittest.mock.patch.dict(__import__('os').environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "PIRN_SIGNING_KEY"):
                _Signer.from_env()


    def test_signer_from_env_empty_raises(self) -> None:
        with unittest.mock.patch.dict(__import__('os').environ, {"PIRN_SIGNING_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "PIRN_SIGNING_KEY"):
                _Signer.from_env()


# ------------------------------------------------------------------ LocalDiskDataStore


    async def test_disk_round_trip_with_signer(self) -> None:
        import tempfile
        _td_test_disk_round_trip_with_signer = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_disk_round_trip_with_signer.cleanup)
        tmp_path = Path(_td_test_disk_round_trip_with_signer.name)
        store = LocalDiskDataStore(tmp_path, signer=_SIGNER)
        await store.put("sha256:abc123", {"x": 1})
        result = await store.get("sha256:abc123")
        assert result == {"x": 1}
    
    
    async def test_disk_tampered_payload_raises(self) -> None:
        import tempfile
        _td_test_disk_tampered_payload_raises = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_disk_tampered_payload_raises.cleanup)
        tmp_path = Path(_td_test_disk_tampered_payload_raises.name)
        store = LocalDiskDataStore(tmp_path, signer=_SIGNER)
        await store.put("sha256:abc123", {"x": 1})
    
        path = Path(store._object_key("sha256:abc123"))
        data = bytearray(path.read_bytes())
        data[-1] ^= 0xFF
        path.write_bytes(bytes(data))
    
        with self.assertRaisesRegex(ValueError, "HMAC signature mismatch"):
            await store.get("sha256:abc123")
    
    
    async def test_disk_unsigned_payload_raises_when_signer_set(self) -> None:
        import tempfile
        _td_test_disk_unsigned_payload_raises_when_signer_set = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_disk_unsigned_payload_raises_when_signer_set.cleanup)
        tmp_path = Path(_td_test_disk_unsigned_payload_raises_when_signer_set.name)
        unsigned_store = LocalDiskDataStore(tmp_path, allow_unsigned=True)
        await unsigned_store.put("sha256:abc123", {"x": 1})
    
        signed_store = LocalDiskDataStore(tmp_path, signer=_SIGNER)
        with self.assertRaisesRegex(ValueError, r"too short|HMAC signature mismatch"):
            await signed_store.get("sha256:abc123")
    
    
    async def test_disk_no_signer_works(self) -> None:
        import tempfile
        _td_test_disk_no_signer_works = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_disk_no_signer_works.cleanup)
        tmp_path = Path(_td_test_disk_no_signer_works.name)
        store = LocalDiskDataStore(tmp_path, allow_unsigned=True)
        await store.put("sha256:abc123", [1, 2, 3])
        assert await store.get("sha256:abc123") == [1, 2, 3]
    
    
    async def test_disk_uses_cloudpickle(self) -> None:
        import tempfile
        _td_test_disk_uses_cloudpickle = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_disk_uses_cloudpickle.cleanup)
        tmp_path = Path(_td_test_disk_uses_cloudpickle.name)
        store = LocalDiskDataStore(tmp_path, allow_unsigned=True)
        await store.put("sha256:abc123", 42)
        path = Path(store._object_key("sha256:abc123"))
        raw = path.read_bytes()
        assert raw[0:1] == b"\x80"
    
    
    def test_disk_refuses_unsigned_without_explicit_opt_in(self) -> None:
        import tempfile
        _td_test_disk_refuses_unsigned_without_explicit_opt_in = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_disk_refuses_unsigned_without_explicit_opt_in.cleanup)
        tmp_path = Path(_td_test_disk_refuses_unsigned_without_explicit_opt_in.name)
        """Constructing without signer or allow_unsigned must raise."""
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            LocalDiskDataStore(tmp_path)
    
    
# ------------------------------------------------------------------ S3DataStore


    async def test_s3_round_trip_with_signer(self) -> None:
        from pirn.backends.s3 import S3DataStore
    
        stored: dict[str, bytes] = {}
        mock_s3 = AsyncMock()
    
        async def fake_put_object(**kwargs: Any) -> None:
            stored[kwargs["Key"]] = kwargs["Body"]
    
        async def fake_get_object(**kwargs: Any) -> dict[str, Any]:
            body_mock = AsyncMock()
            body_mock.read = AsyncMock(return_value=stored[kwargs["Key"]])
            return {"Body": body_mock}
    
        mock_s3.put_object = fake_put_object
        mock_s3.get_object = fake_get_object
    
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_s3)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.client = MagicMock(return_value=ctx)
    
        store = S3DataStore(bucket="test-bucket", session=mock_session, signer=_SIGNER)
        await store.put("sha256:abc", {"y": 2})
        assert await store.get("sha256:abc") == {"y": 2}
    
    
    async def test_s3_tampered_payload_raises(self) -> None:
        from pirn.backends.s3 import S3DataStore
    
        stored: dict[str, bytes] = {}
        mock_s3 = AsyncMock()
    
        async def fake_put_object(**kwargs: Any) -> None:
            data = bytearray(kwargs["Body"])
            data[-1] ^= 0xFF
            stored[kwargs["Key"]] = bytes(data)
    
        async def fake_get_object(**kwargs: Any) -> dict[str, Any]:
            body_mock = AsyncMock()
            body_mock.read = AsyncMock(return_value=stored[kwargs["Key"]])
            return {"Body": body_mock}
    
        mock_s3.put_object = fake_put_object
        mock_s3.get_object = fake_get_object
    
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_s3)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.client = MagicMock(return_value=ctx)
    
        store = S3DataStore(bucket="test-bucket", session=mock_session, signer=_SIGNER)
        await store.put("sha256:abc", {"y": 2})
        with self.assertRaisesRegex(ValueError, "HMAC signature mismatch"):
            await store.get("sha256:abc")
    
    
    async def test_s3_no_signer_works(self) -> None:
        from pirn.backends.s3 import S3DataStore
    
        stored: dict[str, bytes] = {}
        mock_s3 = AsyncMock()
    
        async def fake_put_object(**kwargs: Any) -> None:
            stored[kwargs["Key"]] = kwargs["Body"]
    
        async def fake_get_object(**kwargs: Any) -> dict[str, Any]:
            body_mock = AsyncMock()
            body_mock.read = AsyncMock(return_value=stored[kwargs["Key"]])
            return {"Body": body_mock}
    
        mock_s3.put_object = fake_put_object
        mock_s3.get_object = fake_get_object
    
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_s3)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.client = MagicMock(return_value=ctx)
    
        store = S3DataStore(
            bucket="test-bucket", session=mock_session, allow_unsigned=True
        )
        await store.put("sha256:abc", 99)
        assert await store.get("sha256:abc") == 99
    
    
    def test_s3_refuses_unsigned_without_explicit_opt_in(self) -> None:
        from pirn.backends.s3 import S3DataStore
    
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            S3DataStore(bucket="test-bucket")
    
    
# ------------------------------------------------------------------ ValKeyDataStore


    async def test_valkey_round_trip_with_signer(self) -> None:
        from pirn.backends.valkey.valkey_data_store import ValKeyDataStore
    
        stored: dict[str, bytes] = {}
        mock_client = AsyncMock()
        mock_client.set = AsyncMock(side_effect=lambda k, v, **kw: stored.__setitem__(k, v))
        mock_client.get = AsyncMock(side_effect=lambda k: stored.get(k))
    
        store = ValKeyDataStore(client=mock_client, signer=_SIGNER)
        await store.put("sha256:abc", "hello")
        assert await store.get("sha256:abc") == "hello"
    
    
    async def test_valkey_tampered_payload_raises(self) -> None:
        from pirn.backends.valkey.valkey_data_store import ValKeyDataStore
    
        stored: dict[str, bytes] = {}
    
        async def fake_set(k: str, v: bytes, **kw: Any) -> None:
            data = bytearray(v)
            data[-1] ^= 0xFF
            stored[k] = bytes(data)
    
        mock_client = AsyncMock()
        mock_client.set = fake_set
        mock_client.get = AsyncMock(side_effect=lambda k: stored.get(k))
    
        store = ValKeyDataStore(client=mock_client, signer=_SIGNER)
        await store.put("sha256:abc", "hello")
        with self.assertRaisesRegex(ValueError, "HMAC signature mismatch"):
            await store.get("sha256:abc")
    
    
    async def test_valkey_no_signer_works(self) -> None:
        from pirn.backends.valkey.valkey_data_store import ValKeyDataStore
    
        stored: dict[str, bytes] = {}
        mock_client = AsyncMock()
        mock_client.set = AsyncMock(side_effect=lambda k, v, **kw: stored.__setitem__(k, v))
        mock_client.get = AsyncMock(side_effect=lambda k: stored.get(k))
    
        store = ValKeyDataStore(client=mock_client, allow_unsigned=True)
        await store.put("sha256:abc", [1, 2])
        assert await store.get("sha256:abc") == [1, 2]
    
    
    def test_valkey_refuses_unsigned_without_explicit_opt_in(self) -> None:
        from pirn.backends.valkey.valkey_data_store import ValKeyDataStore
    
        mock_client = AsyncMock()
        with self.assertRaisesRegex(ValueError, "refusing to construct an unsigned"):
            ValKeyDataStore(client=mock_client)
    
    
    def test_signer_test_helper_returns_consistent_signer(self) -> None:
        """test_signer() must return a deterministic signer for unit tests."""
        a = _Signer.test_signer()
        b = _Signer.test_signer()
        payload = b"some payload"
        # Same key → same signature → cross-instance verify must succeed.
        signed = a.sign(payload)
        assert b.verify(signed) == payload
