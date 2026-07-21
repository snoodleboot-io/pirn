"""Security tests for the three chunking loaders (SSRF + path traversal).

`_LoadAndChunk`, `_QALoadAndChunk` and `_TranslationLoadAndChunk` previously
fetched arbitrary URLs and read arbitrary local paths with no guard at all
(PIR-740). They now read through the shared `_DocumentSourceReader`, so this
file asserts each one enforces the same policy `_DocumentLoader` always did.

Every case here runs without the optional ``web`` extra installed — the guard
must reject before httpx is ever resolved.
"""

from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Any, NoReturn

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.document_processing._load_and_chunk import _LoadAndChunk
from pirn_agents.specializations.document_processing._qa_load_and_chunk import (
    _QALoadAndChunk,
)
from pirn_agents.specializations.document_processing._translation_load_and_chunk import (
    _TranslationLoadAndChunk,
)

_READER = "pirn_agents.specializations.document_processing._document_source_reader"
_RESOLVE = "pirn_agents.tools.web._ssrf_guard.SsrfGuard._resolve_all"
_REQUIRE = f"{_READER}._require"

_LOADERS: tuple[type[Knot], ...] = (
    _LoadAndChunk,
    _QALoadAndChunk,
    _TranslationLoadAndChunk,
)


def _build(loader_cls: type[Knot]) -> Any:
    with Tapestry():
        return loader_cls(
            source="placeholder",
            chunk_size=10,
            _config=KnotConfig(id="chunk"),
        )


class TestChunkingLoaderSsrfGuards(unittest.IsolatedAsyncioTestCase):
    async def test_private_and_metadata_hosts_rejected(self) -> None:
        for loader_cls in _LOADERS:
            for host_ip in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "172.16.0.1"):
                with self.subTest(loader=loader_cls.__name__, ip=host_ip):
                    loader = _build(loader_cls)
                    with unittest.mock.patch(
                        _RESOLVE, staticmethod(lambda host, _ip=host_ip: (_ip,))
                    ):
                        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                            await loader.process(source="http://internal.example/", chunk_size=10)

    async def test_host_outside_allowlist_rejected(self) -> None:
        for loader_cls in _LOADERS:
            with self.subTest(loader=loader_cls.__name__):
                loader = _build(loader_cls)
                with unittest.mock.patch(_RESOLVE, staticmethod(lambda host: ("93.184.216.34",))):
                    with self.assertRaisesRegex(ValueError, "not in allowed_hosts"):
                        await loader.process(
                            source="http://other.example/",
                            chunk_size=10,
                            allowed_hosts=("example.com",),
                        )

    async def test_guard_rejects_before_optional_extra_is_resolved(self) -> None:
        """The guard must fire without the ``web`` extra, on every loader."""

        def _no_extra(extra: str, module: str) -> NoReturn:
            raise ImportError(f"{module!r} is required for this feature")

        for loader_cls in _LOADERS:
            with self.subTest(loader=loader_cls.__name__):
                loader = _build(loader_cls)
                with unittest.mock.patch(_RESOLVE, staticmethod(lambda host: ("169.254.169.254",))):
                    with unittest.mock.patch(_REQUIRE, _no_extra):
                        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
                            await loader.process(
                                source="http://169.254.169.254/latest/meta-data/",
                                chunk_size=10,
                            )

    async def test_unsupported_scheme_rejected(self) -> None:
        for loader_cls in _LOADERS:
            with self.subTest(loader=loader_cls.__name__):
                loader = _build(loader_cls)
                with self.assertRaisesRegex(ValueError, "unsupported source scheme"):
                    await loader.process(source="ftp://example.com/x", chunk_size=10)


class TestChunkingLoaderPathGuards(unittest.IsolatedAsyncioTestCase):
    async def test_local_read_without_allowed_root_rejected(self) -> None:
        for loader_cls in _LOADERS:
            with self.subTest(loader=loader_cls.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    document = Path(tmpdir) / "doc.txt"
                    document.write_text("secret", encoding="utf-8")
                    loader = _build(loader_cls)
                    with self.assertRaisesRegex(ValueError, "allowed_root"):
                        await loader.process(source=str(document), chunk_size=10)

    async def test_traversal_outside_allowed_root_rejected(self) -> None:
        for loader_cls in _LOADERS:
            with self.subTest(loader=loader_cls.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    sandbox = Path(tmpdir) / "sandbox"
                    sandbox.mkdir()
                    outside = Path(tmpdir) / "outside.txt"
                    outside.write_text("classified", encoding="utf-8")
                    loader = _build(loader_cls)
                    traversal = sandbox / ".." / "outside.txt"
                    with self.assertRaisesRegex(ValueError, "outside allowed_root"):
                        await loader.process(
                            source=str(traversal),
                            chunk_size=10,
                            allowed_root=str(sandbox),
                        )

    async def test_oversize_file_rejected(self) -> None:
        for loader_cls in _LOADERS:
            with self.subTest(loader=loader_cls.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    document = Path(tmpdir) / "big.txt"
                    document.write_text("x" * 500, encoding="utf-8")
                    loader = _build(loader_cls)
                    with self.assertRaisesRegex(ValueError, "exceeds max_bytes"):
                        await loader.process(
                            source=str(document),
                            chunk_size=10,
                            allowed_root=tmpdir,
                            max_bytes=100,
                        )

    async def test_read_within_allowed_root_succeeds(self) -> None:
        for loader_cls in _LOADERS:
            with self.subTest(loader=loader_cls.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    document = Path(tmpdir) / "doc.txt"
                    document.write_text("abcdefghij", encoding="utf-8")
                    loader = _build(loader_cls)
                    result = await loader.process(
                        source=str(document), chunk_size=5, allowed_root=tmpdir
                    )
                    assert result == ["abcde", "fghij"]
