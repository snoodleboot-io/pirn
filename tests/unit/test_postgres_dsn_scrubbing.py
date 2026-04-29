"""Tests for DSN credential sanitization in the postgres backend (M-4)."""

from __future__ import annotations

import pytest

from pirn.backends.postgres._lazy_pool import _sanitize_dsn


def test_sanitize_dsn_with_user_and_password() -> None:
    result = _sanitize_dsn("postgresql://user:s3cr3t@host/db")
    assert result == "postgresql://<redacted>@host/db"
    assert "s3cr3t" not in result


def test_sanitize_dsn_without_credentials() -> None:
    dsn = "postgresql://host/db"
    assert _sanitize_dsn(dsn) == dsn


def test_sanitize_dsn_with_port_and_options() -> None:
    result = _sanitize_dsn("postgresql://user:pass@host:5432/db?sslmode=require")
    assert result == "postgresql://<redacted>@host:5432/db?sslmode=require"
    assert "pass" not in result


@pytest.mark.asyncio
async def test_create_pool_error_does_not_leak_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """When asyncpg.create_pool raises with DSN in the message, password is redacted."""
    import asyncpg

    dsn = "postgresql://admin:topsecret@localhost/mydb"

    async def _fake_create_pool(d: str, **_: object) -> None:
        raise OSError(f"could not connect to server: {d}")

    monkeypatch.setattr(asyncpg, "create_pool", _fake_create_pool)

    from pirn.backends.postgres._lazy_pool import _LazyPool

    lazy = _LazyPool(dsn=dsn)
    with pytest.raises(OSError) as exc_info:
        await lazy.get()

    assert "topsecret" not in str(exc_info.value)
    assert "<redacted>" in str(exc_info.value)
