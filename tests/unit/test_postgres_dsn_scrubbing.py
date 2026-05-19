"""Tests for DSN credential sanitization in the postgres backend (M-4)."""

from __future__ import annotations
import unittest




class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    def test_sanitize_dsn_with_user_and_password(self) -> None:
        from pirn.backends.postgres._lazy_pool import _LazyPool
    
        pool = _LazyPool(dsn="postgresql://user:s3cr3t@host/db")
        assert pool._dsn_display == "postgresql://<redacted>@host/db"
        assert "s3cr3t" not in pool._dsn_display
    
    
    def test_sanitize_dsn_without_credentials(self) -> None:
        from pirn.backends.postgres._lazy_pool import _LazyPool
    
        dsn = "postgresql://host/db"
        pool = _LazyPool(dsn=dsn)
        assert pool._dsn_display == dsn
    
    
    def test_sanitize_dsn_with_port_and_options(self) -> None:
        from pirn.backends.postgres._lazy_pool import _LazyPool
    
        pool = _LazyPool(dsn="postgresql://user:pass@host:5432/db?sslmode=require")
        assert pool._dsn_display == "postgresql://<redacted>@host:5432/db?sslmode=require"
        assert "pass" not in pool._dsn_display
    
    
    async def test_create_pool_error_does_not_leak_password(self) -> None:
        """When asyncpg.create_pool raises with DSN in the message, password is redacted."""
        import pytest
        asyncpg = pytest.importorskip("asyncpg")
    
        dsn = "postgresql://admin:topsecret@localhost/mydb"
    
        async def _fake_create_pool(d: str, **_: object) -> None:
            raise OSError(f"could not connect to server: {d}")
    
        with unittest.mock.patch.object(asyncpg, "create_pool", _fake_create_pool):
            from pirn.backends.postgres._lazy_pool import _LazyPool
            lazy = _LazyPool(dsn=dsn)
            with self.assertRaises(OSError) as exc_info:
                await lazy.get()

        assert "topsecret" not in str(exc_info.exception)
        assert "<redacted>" in str(exc_info.exception)
