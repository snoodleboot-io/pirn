"""Unit tests for :class:`_DocumentSourceReader`, the shared guarded reader.

The four document loaders delegate their whole security contract here, so the
policy is pinned directly rather than only through its callers.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn_agents.specializations.document_processing._document_source_reader import (
    _DocumentSourceReader,
)


class TestMaxBytesValidation(unittest.TestCase):
    def test_rejects_non_positive(self) -> None:
        for value in (0, -1):
            with self.subTest(max_bytes=value):
                with self.assertRaisesRegex(ValueError, "positive int"):
                    _DocumentSourceReader(max_bytes=value)

    def test_rejects_non_int(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be an int"):
            _DocumentSourceReader(max_bytes="big")  # type: ignore[arg-type]

    def test_rejects_bool(self) -> None:
        # bool is an int subclass; True would otherwise pass as max_bytes=1.
        with self.assertRaisesRegex(TypeError, "must be an int"):
            _DocumentSourceReader(max_bytes=True)


class TestSchemeDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_source(self) -> None:
        with self.assertRaisesRegex(TypeError, "non-empty string"):
            await _DocumentSourceReader().read("")

    async def test_rejects_unsupported_scheme(self) -> None:
        for source in ("ftp://example.com/x", "javascript:alert(1)", "data:text/plain;base64,eA=="):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "unsupported source scheme"):
                    await _DocumentSourceReader().read(source)

    async def test_file_scheme_uses_path_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            document = Path(tmpdir) / "doc.txt"
            document.write_text("hello", encoding="utf-8")
            reader = _DocumentSourceReader(allowed_root=tmpdir)
            assert await reader.read(f"file://{document}") == "hello"

    async def test_url_without_hostname_rejected(self) -> None:
        with self.assertRaises(ValueError):
            await _DocumentSourceReader().read("http:///nohost")


class TestHostPolicy(unittest.IsolatedAsyncioTestCase):
    """The resolver is injected, so these never touch DNS."""

    async def test_private_ip_rejected(self) -> None:
        reader = _DocumentSourceReader(resolver=lambda host: "10.0.0.1")
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            await reader.read("http://internal.example/")

    async def test_metadata_endpoint_rejected(self) -> None:
        reader = _DocumentSourceReader(resolver=lambda host: "169.254.169.254")
        with self.assertRaisesRegex(ValueError, "private/loopback/link-local"):
            await reader.read("http://169.254.169.254/latest/meta-data/")

    async def test_unresolvable_host_rejected(self) -> None:
        def _boom(host: str) -> str:
            raise OSError("dns failure")

        reader = _DocumentSourceReader(resolver=_boom)
        with self.assertRaisesRegex(ValueError, "unresolvable host"):
            await reader.read("http://nope.invalid/")

    async def test_empty_allowed_hosts_denies_everything(self) -> None:
        # () is a deny-all policy, distinct from None ("no allow-list").
        reader = _DocumentSourceReader(allowed_hosts=(), resolver=lambda host: "93.184.216.34")
        with self.assertRaisesRegex(ValueError, "not in allowed_hosts"):
            await reader.read("http://example.com/")


class TestAuditDict(unittest.TestCase):
    def test_empty_allowed_hosts_is_not_reported_as_no_policy(self) -> None:
        assert _DocumentSourceReader(allowed_hosts=())._pirn_audit_dict()["allowed_hosts"] == []
        assert _DocumentSourceReader(allowed_hosts=None)._pirn_audit_dict()["allowed_hosts"] is None

    def test_reports_policy(self) -> None:
        audit = _DocumentSourceReader(
            allowed_root="/srv/docs", allowed_hosts=("example.com",), max_bytes=1024
        )._pirn_audit_dict()
        assert audit["allowed_root"] == "/srv/docs"
        assert audit["allowed_hosts"] == ["example.com"]
        assert audit["max_bytes"] == 1024

    def test_resolver_excluded_from_equality(self) -> None:
        # Two readers with the same policy are equal regardless of resolver identity.
        assert _DocumentSourceReader(resolver=lambda h: "1.1.1.1") == _DocumentSourceReader()


class TestPathPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_local_read_requires_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            document = Path(tmpdir) / "doc.txt"
            document.write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "require allowed_root"):
                await _DocumentSourceReader().read(str(document))

    async def test_symlink_escape_rejected(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = Path(tmpdir) / "sandbox"
            sandbox.mkdir()
            secret = Path(tmpdir) / "secret.txt"
            secret.write_text("classified", encoding="utf-8")
            link = sandbox / "link.txt"
            os.symlink(secret, link)
            reader = _DocumentSourceReader(allowed_root=str(sandbox))
            with self.assertRaisesRegex(ValueError, "outside allowed_root"):
                await reader.read(str(link))

    async def test_oversize_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            document = Path(tmpdir) / "big.txt"
            document.write_text("x" * 500, encoding="utf-8")
            reader = _DocumentSourceReader(allowed_root=tmpdir, max_bytes=100)
            with self.assertRaisesRegex(ValueError, "exceeds max_bytes"):
                await reader.read(str(document))
