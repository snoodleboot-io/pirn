"""Security tests for :class:`_DocumentLoader` (path traversal + SSRF)."""

from __future__ import annotations

import os
import tempfile
import unittest
import unittest.mock
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, ClassVar, NoReturn

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._document_loader import (
    _DocumentLoader,
)


def _build_loader() -> _DocumentLoader:
    with Tapestry():
        return _DocumentLoader(
            source="placeholder",
            _config=KnotConfig(id="load"),
        )


class TestPathTraversalGuards(unittest.IsolatedAsyncioTestCase):
    async def test_local_read_without_allowed_root_raises(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        document = tmp_path / "doc.txt"
        document.write_text("hello", encoding="utf-8")
        loader = _build_loader()
        with self.assertRaisesRegex(ValueError, "allowed_root"):
            await loader.process(str(document))

    async def test_local_read_outside_allowed_root_raises(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("oops", encoding="utf-8")
        loader = _build_loader()
        traversal = sandbox / ".." / "outside.txt"
        with self.assertRaisesRegex(ValueError, "outside allowed_root"):
            await loader.process(str(traversal), allowed_root=str(sandbox))

    async def test_symlink_escape_raises(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        outside = tmp_path / "secret.txt"
        outside.write_text("classified", encoding="utf-8")
        link = sandbox / "link.txt"
        os.symlink(outside, link)
        loader = _build_loader()
        # Resolved target escapes; rejected by allowed_root check.
        with self.assertRaisesRegex(ValueError, "outside allowed_root"):
            await loader.process(str(link), allowed_root=str(sandbox))

    async def test_oversize_file_raises(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        document = tmp_path / "big.txt"
        document.write_text("x" * 500, encoding="utf-8")
        loader = _build_loader()
        with self.assertRaisesRegex(ValueError, "exceeds max_bytes"):
            await loader.process(str(document), allowed_root=str(tmp_path), max_bytes=100)

    async def test_unsupported_scheme_raises(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        loader = _build_loader()
        for source in (
            "javascript:alert(1)",
            "data:text/plain;base64,SGVsbG8=",
            "ftp://example.com/x",
        ):
            with self.assertRaisesRegex(ValueError, "unsupported source scheme"):
                await loader.process(source, allowed_root=str(tmp_path))

    async def test_file_scheme_uses_path_validation(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        tmp_path = Path(_td.name)
        document = tmp_path / "doc.txt"
        document.write_text("hi", encoding="utf-8")
        loader = _build_loader()
        with self.assertRaisesRegex(ValueError, "allowed_root"):
            await loader.process(f"file://{document}")


class TestSSRFGuards(unittest.IsolatedAsyncioTestCase):
    async def test_loopback_url_raises(self) -> None:
        loader = _build_loader()
        with unittest.mock.patch(
            "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all",
            staticmethod(lambda host: ("127.0.0.1",)),
        ):
            with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                await loader.process("http://localhost/")

    async def test_private_ip_raises(self) -> None:
        loader = _build_loader()
        with unittest.mock.patch(
            "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all",
            staticmethod(lambda host: ("10.0.0.1",)),
        ):
            with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                await loader.process("http://internal.example/")

    async def test_imds_metadata_raises(self) -> None:
        loader = _build_loader()
        with unittest.mock.patch(
            "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all",
            staticmethod(lambda host: ("169.254.169.254",)),
        ):
            with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                await loader.process("http://169.254.169.254/latest/meta-data/")

    async def test_unresolvable_host_raises(self) -> None:
        import socket as _socket

        loader = _build_loader()

        def _boom(host: str) -> str:
            raise _socket.gaierror("dns failure")

        with unittest.mock.patch(
            "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all",
            staticmethod(_boom),
        ):
            with self.assertRaisesRegex(ValueError, "unresolvable host"):
                await loader.process("http://nope.invalid/")

    async def test_host_not_in_allowlist_raises(self) -> None:
        loader = _build_loader()
        with unittest.mock.patch(
            "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all",
            staticmethod(lambda host: ("93.184.216.34",)),
        ):
            with self.assertRaisesRegex(ValueError, "not in allowed_hosts"):
                await loader.process("http://other.example/", allowed_hosts=("example.com",))

    async def test_guard_rejects_before_optional_extra_is_resolved(self) -> None:
        """The SSRF guard must fire even when the ``web`` extra is absent.

        Regression test for the ordering bug where ``_require("web", "httpx")`` ran
        ahead of the guard, so a hostile URL raised ImportError instead of ValueError
        on an install without the extra. Forces the missing-extra path regardless of
        whether httpx happens to be installed, so CI pins the ordering too.
        """
        loader = _build_loader()

        def _no_extra(extra: str, module: str) -> NoReturn:
            raise ImportError(f"{module!r} is required for this feature")

        require_path = (
            "pirn_agents.specializations.document_processing._document_source_reader._require"
        )
        # Both rejection paths, so _require cannot be relocated between them.
        with unittest.mock.patch(
            "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all",
            staticmethod(lambda host: ("169.254.169.254",)),
        ):
            with unittest.mock.patch(require_path, _no_extra):
                with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                    await loader.process("http://169.254.169.254/latest/meta-data/")

        with unittest.mock.patch(
            "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all",
            staticmethod(lambda host: ("93.184.216.34",)),
        ):
            with unittest.mock.patch(require_path, _no_extra):
                with self.assertRaisesRegex(ValueError, "not in allowed_hosts"):
                    await loader.process("http://other.example/", allowed_hosts=("example.com",))

    async def test_allowed_host_passes(self) -> None:
        # The only test here that needs the optional ``web`` extra: it stubs
        # ``httpx.AsyncClient`` to exercise the post-guard fetch path. The SSRF
        # rejection tests above deliberately require no extra.
        httpx = pytest.importorskip("httpx")
        loader = _build_loader()

        class _StubResponse:
            """Mirrors the streamed-response surface the reader consumes."""

            is_redirect = False
            encoding = "utf-8"
            headers: ClassVar[dict[str, str]] = {}

            def raise_for_status(self) -> None:
                return None

            async def aiter_bytes(self) -> AsyncIterator[bytes]:
                yield b"ok"

            async def __aenter__(self) -> _StubResponse:
                return self

            async def __aexit__(self, *args: Any) -> None:
                return None

        class _StubAsyncClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.kwargs = kwargs

            async def __aenter__(self) -> _StubAsyncClient:
                return self

            async def __aexit__(self, *args: Any) -> None:
                return None

            def stream(self, method: str, url: str) -> _StubResponse:
                return _StubResponse()

        with unittest.mock.patch(
            "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all",
            staticmethod(lambda host: ("93.184.216.34",)),
        ):
            with unittest.mock.patch.object(httpx, "AsyncClient", _StubAsyncClient):
                result = await loader.process(
                    "http://example.com/",
                    allowed_hosts=("example.com",),
                )
        assert result == "ok"
