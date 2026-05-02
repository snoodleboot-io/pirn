"""Security tests for :class:`_DocumentLoader` (path traversal + SSRF)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.document_processing._document_loader import (  # noqa: E501
    _DocumentLoader,
)
from pirn.tapestry import Tapestry


def _build_loader(
    *,
    source: str = "placeholder",
    allowed_root: str | None = None,
    allowed_hosts: tuple[str, ...] | None = None,
    max_bytes: int = 100 * 1024 * 1024,
) -> _DocumentLoader:
    with Tapestry():
        loader = _DocumentLoader(
            source=source,
            allowed_root=allowed_root,
            allowed_hosts=allowed_hosts,
            max_bytes=max_bytes,
            _config=KnotConfig(id="load"),
        )
    return loader


@pytest.mark.asyncio
class TestPathTraversalGuards:
    async def test_local_read_without_allowed_root_raises(
        self, tmp_path: Path
    ) -> None:
        document = tmp_path / "doc.txt"
        document.write_text("hello", encoding="utf-8")
        loader = _build_loader()
        with pytest.raises(ValueError, match="allowed_root"):
            await loader.process(str(document))

    async def test_local_read_outside_allowed_root_raises(
        self, tmp_path: Path
    ) -> None:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("oops", encoding="utf-8")
        loader = _build_loader(allowed_root=str(sandbox))
        # Try to escape via ``..``.
        traversal = sandbox / ".." / "outside.txt"
        with pytest.raises(ValueError, match="outside allowed_root"):
            await loader.process(str(traversal))

    async def test_symlink_escape_raises(self, tmp_path: Path) -> None:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        outside = tmp_path / "secret.txt"
        outside.write_text("classified", encoding="utf-8")
        link = sandbox / "link.txt"
        os.symlink(outside, link)
        loader = _build_loader(allowed_root=str(sandbox))
        # Resolved target escapes; rejected by allowed_root check.
        with pytest.raises(ValueError, match="outside allowed_root"):
            await loader.process(str(link))

    async def test_oversize_file_raises(self, tmp_path: Path) -> None:
        document = tmp_path / "big.txt"
        document.write_text("x" * 500, encoding="utf-8")
        loader = _build_loader(allowed_root=str(tmp_path), max_bytes=100)
        with pytest.raises(ValueError, match="exceeds max_bytes"):
            await loader.process(str(document))

    async def test_unsupported_scheme_raises(self, tmp_path: Path) -> None:
        loader = _build_loader(allowed_root=str(tmp_path))
        for source in (
            "javascript:alert(1)",
            "data:text/plain;base64,SGVsbG8=",
            "ftp://example.com/x",
        ):
            with pytest.raises(ValueError, match="unsupported source scheme"):
                await loader.process(source)

    async def test_file_scheme_uses_path_validation(
        self, tmp_path: Path
    ) -> None:
        # ``file://`` URLs route into the local-file path; without
        # allowed_root they must still be rejected.
        document = tmp_path / "doc.txt"
        document.write_text("hi", encoding="utf-8")
        loader = _build_loader()
        with pytest.raises(ValueError, match="allowed_root"):
            await loader.process(f"file://{document}")


@pytest.mark.asyncio
class TestSSRFGuards:
    async def test_loopback_url_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        loader = _build_loader(allowed_root=str(tmp_path))
        monkeypatch.setattr(
            "pirn.domains.agents.specializations.document_processing."
            "_document_loader.socket.gethostbyname",
            lambda host: "127.0.0.1",
        )
        with pytest.raises(ValueError, match="private/loopback/link-local"):
            await loader.process("http://localhost/")

    async def test_private_ip_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        loader = _build_loader(allowed_root=str(tmp_path))
        monkeypatch.setattr(
            "pirn.domains.agents.specializations.document_processing."
            "_document_loader.socket.gethostbyname",
            lambda host: "10.0.0.1",
        )
        with pytest.raises(ValueError, match="private/loopback/link-local"):
            await loader.process("http://internal.example/")

    async def test_imds_metadata_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        loader = _build_loader(allowed_root=str(tmp_path))
        monkeypatch.setattr(
            "pirn.domains.agents.specializations.document_processing."
            "_document_loader.socket.gethostbyname",
            lambda host: "169.254.169.254",
        )
        with pytest.raises(ValueError, match="private/loopback/link-local"):
            await loader.process("http://169.254.169.254/latest/meta-data/")

    async def test_unresolvable_host_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import socket as _socket

        loader = _build_loader(allowed_root=str(tmp_path))

        def _boom(host: str) -> str:
            raise _socket.gaierror("dns failure")

        monkeypatch.setattr(
            "pirn.domains.agents.specializations.document_processing."
            "_document_loader.socket.gethostbyname",
            _boom,
        )
        with pytest.raises(ValueError, match="unresolvable host"):
            await loader.process("http://nope.invalid/")

    async def test_host_not_in_allowlist_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        loader = _build_loader(
            allowed_root=str(tmp_path),
            allowed_hosts=("example.com",),
        )
        monkeypatch.setattr(
            "pirn.domains.agents.specializations.document_processing."
            "_document_loader.socket.gethostbyname",
            lambda host: "93.184.216.34",
        )
        with pytest.raises(ValueError, match="not in allowed_hosts"):
            await loader.process("http://other.example/")

    async def test_allowed_host_passes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        loader = _build_loader(
            allowed_root=str(tmp_path),
            allowed_hosts=("example.com",),
        )
        monkeypatch.setattr(
            "pirn.domains.agents.specializations.document_processing."
            "_document_loader.socket.gethostbyname",
            lambda host: "93.184.216.34",
        )

        # Stub httpx.AsyncClient so we don't touch the network.
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

        monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)
        result = await loader.process("http://example.com/")
        assert result == "ok"
