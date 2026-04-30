"""Tests for HMAC signing on DataStore backends (findings C-1 and I-14)."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pirn.backends._signer import _Signer
from pirn.backends.disk import LocalDiskDataStore

_KEY = b"test-signing-key-32-bytes-abcdefg"[:32]
_SIGNER = _Signer(_KEY)


# ------------------------------------------------------------------ _Signer


def test_sign_verify_round_trip() -> None:
    payload = b"hello world"
    signed = _SIGNER.sign(payload)
    assert _SIGNER.verify(signed) == payload


def test_verify_too_short_raises() -> None:
    with pytest.raises(ValueError, match="too short"):
        _SIGNER.verify(b"\x00" * 10)


def test_verify_tampered_raises() -> None:
    signed = _SIGNER.sign(b"data")
    tampered = bytearray(signed)
    tampered[-1] ^= 0xFF
    with pytest.raises(ValueError, match="HMAC signature mismatch"):
        _SIGNER.verify(bytes(tampered))


def test_signer_from_env_reads_base64(monkeypatch: Any) -> None:
    key = b"exactly-32-bytes-for-hmac-sha256"
    monkeypatch.setenv("PIRN_SIGNING_KEY", base64.b64encode(key).decode())
    signer = _Signer.from_env()
    assert signer.sign(b"x") != b"x"


def test_signer_from_env_custom_var(monkeypatch: Any) -> None:
    key = b"exactly-32-bytes-for-hmac-sha256"
    monkeypatch.setenv("MY_CUSTOM_KEY", base64.b64encode(key).decode())
    signer = _Signer.from_env("MY_CUSTOM_KEY")
    assert signer.sign(b"x") != b"x"


def test_signer_from_env_missing_raises(monkeypatch: Any) -> None:
    monkeypatch.delenv("PIRN_SIGNING_KEY", raising=False)
    with pytest.raises(ValueError, match="PIRN_SIGNING_KEY"):
        _Signer.from_env()


def test_signer_from_env_empty_raises(monkeypatch: Any) -> None:
    monkeypatch.setenv("PIRN_SIGNING_KEY", "")
    with pytest.raises(ValueError, match="PIRN_SIGNING_KEY"):
        _Signer.from_env()


# ------------------------------------------------------------------ LocalDiskDataStore


@pytest.mark.asyncio
async def test_disk_round_trip_with_signer(tmp_path: Any) -> None:
    store = LocalDiskDataStore(tmp_path, signer=_SIGNER)
    await store.put("sha256:abc123", {"x": 1})
    result = await store.get("sha256:abc123")
    assert result == {"x": 1}


@pytest.mark.asyncio
async def test_disk_tampered_payload_raises(tmp_path: Any) -> None:
    store = LocalDiskDataStore(tmp_path, signer=_SIGNER)
    await store.put("sha256:abc123", {"x": 1})

    path = Path(store._object_key("sha256:abc123"))
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))

    with pytest.raises(ValueError, match="HMAC signature mismatch"):
        await store.get("sha256:abc123")


@pytest.mark.asyncio
async def test_disk_unsigned_payload_raises_when_signer_set(tmp_path: Any) -> None:
    unsigned_store = LocalDiskDataStore(tmp_path)
    await unsigned_store.put("sha256:abc123", {"x": 1})

    signed_store = LocalDiskDataStore(tmp_path, signer=_SIGNER)
    with pytest.raises(ValueError, match=r"too short|HMAC signature mismatch"):
        await signed_store.get("sha256:abc123")


@pytest.mark.asyncio
async def test_disk_no_signer_works(tmp_path: Any) -> None:
    store = LocalDiskDataStore(tmp_path)
    await store.put("sha256:abc123", [1, 2, 3])
    assert await store.get("sha256:abc123") == [1, 2, 3]


@pytest.mark.asyncio
async def test_disk_uses_cloudpickle(tmp_path: Any) -> None:
    store = LocalDiskDataStore(tmp_path)
    await store.put("sha256:abc123", 42)
    path = Path(store._object_key("sha256:abc123"))
    raw = path.read_bytes()
    assert raw[0:1] == b"\x80"


# ------------------------------------------------------------------ S3DataStore


@pytest.mark.asyncio
async def test_s3_round_trip_with_signer() -> None:
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


@pytest.mark.asyncio
async def test_s3_tampered_payload_raises() -> None:
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
    with pytest.raises(ValueError, match="HMAC signature mismatch"):
        await store.get("sha256:abc")


@pytest.mark.asyncio
async def test_s3_no_signer_works() -> None:
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

    store = S3DataStore(bucket="test-bucket", session=mock_session)
    await store.put("sha256:abc", 99)
    assert await store.get("sha256:abc") == 99


# ------------------------------------------------------------------ ValKeyDataStore


@pytest.mark.asyncio
async def test_valkey_round_trip_with_signer() -> None:
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    stored: dict[str, bytes] = {}
    mock_client = AsyncMock()
    mock_client.set = AsyncMock(side_effect=lambda k, v, **kw: stored.__setitem__(k, v))
    mock_client.get = AsyncMock(side_effect=lambda k: stored.get(k))

    store = ValKeyDataStore(client=mock_client, signer=_SIGNER)
    await store.put("sha256:abc", "hello")
    assert await store.get("sha256:abc") == "hello"


@pytest.mark.asyncio
async def test_valkey_tampered_payload_raises() -> None:
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
    with pytest.raises(ValueError, match="HMAC signature mismatch"):
        await store.get("sha256:abc")


@pytest.mark.asyncio
async def test_valkey_no_signer_works() -> None:
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    stored: dict[str, bytes] = {}
    mock_client = AsyncMock()
    mock_client.set = AsyncMock(side_effect=lambda k, v, **kw: stored.__setitem__(k, v))
    mock_client.get = AsyncMock(side_effect=lambda k: stored.get(k))

    store = ValKeyDataStore(client=mock_client)
    await store.put("sha256:abc", [1, 2])
    assert await store.get("sha256:abc") == [1, 2]
