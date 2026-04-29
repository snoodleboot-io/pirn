"""Tests for HMAC signing on DataStore backends (findings C-1 and I-14)."""

from __future__ import annotations

import base64
import os
import pickle
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pirn.backends.signing_key import signing_key_from_env
from pirn.backends._signing import sign, verify
from pirn.backends.disk import LocalDiskDataStore

_KEY = b"test-signing-key-32-bytes-abcdefg"[:32]  # 32 bytes


# ------------------------------------------------------------------ _signing helpers


def test_sign_verify_round_trip() -> None:
    payload = b"hello world"
    signed = sign(payload, _KEY)
    assert verify(signed, _KEY) == payload


def test_verify_too_short_raises() -> None:
    with pytest.raises(ValueError, match="too short"):
        verify(b"\x00" * 10, _KEY)


def test_verify_tampered_raises() -> None:
    signed = sign(b"data", _KEY)
    tampered = bytearray(signed)
    tampered[-1] ^= 0xFF
    with pytest.raises(ValueError, match="HMAC signature mismatch"):
        verify(bytes(tampered), _KEY)


# ------------------------------------------------------------------ LocalDiskDataStore


@pytest.mark.asyncio
async def test_disk_round_trip_with_signing_key(tmp_path: Any) -> None:
    store = LocalDiskDataStore(tmp_path, signing_key=_KEY)
    await store.put("sha256:abc123", {"x": 1})
    result = await store.get("sha256:abc123")
    assert result == {"x": 1}


@pytest.mark.asyncio
async def test_disk_tampered_payload_raises(tmp_path: Any) -> None:
    store = LocalDiskDataStore(tmp_path, signing_key=_KEY)
    await store.put("sha256:abc123", {"x": 1})

    # Corrupt the stored file
    path = store._path("sha256:abc123")
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))

    with pytest.raises(ValueError, match="HMAC signature mismatch"):
        await store.get("sha256:abc123")


@pytest.mark.asyncio
async def test_disk_unsigned_payload_raises_when_key_set(tmp_path: Any) -> None:
    """Payload written without a key, read back with a key -> ValueError."""
    unsigned_store = LocalDiskDataStore(tmp_path)
    await unsigned_store.put("sha256:abc123", {"x": 1})

    signed_store = LocalDiskDataStore(tmp_path, signing_key=_KEY)
    with pytest.raises(ValueError, match="too short|HMAC signature mismatch"):
        await signed_store.get("sha256:abc123")


@pytest.mark.asyncio
async def test_disk_no_signing_key_works_as_before(tmp_path: Any) -> None:
    store = LocalDiskDataStore(tmp_path)
    await store.put("sha256:abc123", [1, 2, 3])
    assert await store.get("sha256:abc123") == [1, 2, 3]


@pytest.mark.asyncio
async def test_disk_uses_pickle_protocol_5(tmp_path: Any) -> None:
    store = LocalDiskDataStore(tmp_path)
    await store.put("sha256:abc123", 42)
    path = store._path("sha256:abc123")
    raw = path.read_bytes()
    # Protocol 5 starts with opcode PROTO (0x80) followed by 0x05
    assert raw[:2] == b"\x80\x05"


# ------------------------------------------------------------------ signing_key_from_env


def test_signing_key_from_env_reads_base64(monkeypatch: Any) -> None:
    key = b"exactly-32-bytes-for-hmac-sha256"
    monkeypatch.setenv("PIRN_SIGNING_KEY", base64.b64encode(key).decode())
    assert signing_key_from_env() == key


def test_signing_key_from_env_custom_var(monkeypatch: Any) -> None:
    key = b"exactly-32-bytes-for-hmac-sha256"
    monkeypatch.setenv("MY_CUSTOM_KEY", base64.b64encode(key).decode())
    assert signing_key_from_env("MY_CUSTOM_KEY") == key


def test_signing_key_from_env_missing_raises(monkeypatch: Any) -> None:
    monkeypatch.delenv("PIRN_SIGNING_KEY", raising=False)
    with pytest.raises(ValueError, match="PIRN_SIGNING_KEY"):
        signing_key_from_env()


def test_signing_key_from_env_empty_raises(monkeypatch: Any) -> None:
    monkeypatch.setenv("PIRN_SIGNING_KEY", "")
    with pytest.raises(ValueError, match="PIRN_SIGNING_KEY"):
        signing_key_from_env()


# ------------------------------------------------------------------ S3DataStore (mocked)


@pytest.mark.asyncio
async def test_s3_round_trip_with_signing_key() -> None:
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

    store = S3DataStore(bucket="test-bucket", session=mock_session, signing_key=_KEY)
    await store.put("sha256:abc", {"y": 2})
    result = await store.get("sha256:abc")
    assert result == {"y": 2}


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

    store = S3DataStore(bucket="test-bucket", session=mock_session, signing_key=_KEY)
    await store.put("sha256:abc", {"y": 2})
    with pytest.raises(ValueError, match="HMAC signature mismatch"):
        await store.get("sha256:abc")


@pytest.mark.asyncio
async def test_s3_no_signing_key_works_as_before() -> None:
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


# ------------------------------------------------------------------ ValKeyDataStore (mocked)


@pytest.mark.asyncio
async def test_valkey_round_trip_with_signing_key() -> None:
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    stored: dict[str, bytes] = {}

    mock_client = AsyncMock()
    mock_client.set = AsyncMock(side_effect=lambda k, v, **kw: stored.__setitem__(k, v))
    mock_client.get = AsyncMock(side_effect=lambda k: stored.get(k))

    store = ValKeyDataStore(client=mock_client, signing_key=_KEY)
    await store.put("sha256:abc", "hello")
    result = await store.get("sha256:abc")
    assert result == "hello"


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

    store = ValKeyDataStore(client=mock_client, signing_key=_KEY)
    await store.put("sha256:abc", "hello")
    with pytest.raises(ValueError, match="HMAC signature mismatch"):
        await store.get("sha256:abc")


@pytest.mark.asyncio
async def test_valkey_no_signing_key_works_as_before() -> None:
    from pirn.backends.valkey.valkey_data_store import ValKeyDataStore

    stored: dict[str, bytes] = {}

    mock_client = AsyncMock()
    mock_client.set = AsyncMock(side_effect=lambda k, v, **kw: stored.__setitem__(k, v))
    mock_client.get = AsyncMock(side_effect=lambda k: stored.get(k))

    store = ValKeyDataStore(client=mock_client)
    await store.put("sha256:abc", [1, 2])
    assert await store.get("sha256:abc") == [1, 2]
