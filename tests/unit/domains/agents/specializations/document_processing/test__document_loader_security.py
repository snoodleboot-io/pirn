"""Security tests for :class:`_DocumentLoader` (path traversal + SSRF)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import unittest
import unittest.mock
import tempfile


from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.document_processing._document_loader import (  # noqa: E501
    _DocumentLoader,
)
from pirn.tapestry import Tapestry


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
            "pirn.domains.agents.specializations.document_processing"
            "._document_loader.socket.gethostbyname",
            lambda host: "127.0.0.1",
        ):
            with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                await loader.process("http://localhost/")

    async def test_private_ip_raises(self) -> None:
        loader = _build_loader()
        with unittest.mock.patch(
            "pirn.domains.agents.specializations.document_processing"
            "._document_loader.socket.gethostbyname",
            lambda host: "10.0.0.1",
        ):
            with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                await loader.process("http://internal.example/")

    async def test_imds_metadata_raises(self) -> None:
        loader = _build_loader()
        with unittest.mock.patch(
            "pirn.domains.agents.specializations.document_processing"
            "._document_loader.socket.gethostbyname",
            lambda host: "169.254.169.254",
        ):
            with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                await loader.process("http://169.254.169.254/latest/meta-data/")

    async def test_unresolvable_host_raises(self) -> None:
        import socket as _socket
        loader = _build_loader()

        def _boom(host: str) -> str:
            raise _socket.gaierror("dns failure")

        with unittest.mock.patch(
            "pirn.domains.agents.specializations.document_processing"
            "._document_loader.socket.gethostbyname",
            _boom,
        ):
            with self.assertRaisesRegex(ValueError, "unresolvable host"):
                await loader.process("http://nope.invalid/")

    async def test_host_not_in_allowlist_raises(self) -> None:
        loader = _build_loader()
        with unittest.mock.patch(
            "pirn.domains.agents.specializations.document_processing"
            "._document_loader.socket.gethostbyname",
            lambda host: "93.184.216.34",
        ):
            with self.assertRaisesRegex(ValueError, "not in allowed_hosts"):
                await loader.process("http://other.example/", allowed_hosts=("example.com",))

    async def test_allowed_host_passes(self) -> None:
        loader = _build_loader()

        class _StubResponse:
            text = "ok"

            def raise_for_status(self) -> None:
                return None

        class _StubAsyncClient:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.kwargs = kwargs

            async def __aenter__(self) -> "_StubAsyncClient":
                return self

            async def __aexit__(self, *args: Any) -> None:
                return None

            async def get(self, url: str) -> _StubResponse:
                return _StubResponse()

        import httpx

        with unittest.mock.patch(
            "pirn.domains.agents.specializations.document_processing"
            "._document_loader.socket.gethostbyname",
            lambda host: "93.184.216.34",
        ):
            with unittest.mock.patch.object(httpx, "AsyncClient", _StubAsyncClient):
                result = await loader.process(
                    "http://example.com/",
                    allowed_hosts=("example.com",),
                )
        assert result == "ok"
