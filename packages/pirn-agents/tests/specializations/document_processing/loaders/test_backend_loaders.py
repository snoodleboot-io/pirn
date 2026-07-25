"""Tests for the backend-backed loaders (F25-S1): PDF, HTML, docx.

The parser backends (``pypdf``, ``bs4``, ``docx``) are optional extras and are
not installed in the base test env, so each happy-path test injects a tiny fake
backend module into :data:`sys.modules` (offline, deterministic). The
missing-backend path is forced with ``patch.dict(sys.modules, {mod: None})`` so
it is asserted regardless of what is installed.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from pirn_agents.specializations.document_processing.loaders.docx_loader import DocxLoader
from pirn_agents.specializations.document_processing.loaders.html_loader import HtmlLoader
from pirn_agents.specializations.document_processing.loaders.pdf_loader import PdfLoader


def _fake_pypdf(pages: list[str], *, raise_on_read: bool = False) -> types.ModuleType:
    module = types.ModuleType("pypdf")

    class _Page:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _Reader:
        def __init__(self, _stream: object) -> None:
            if raise_on_read:
                raise ValueError("corrupt pdf")
            self.pages = [_Page(text) for text in pages]

    module.PdfReader = _Reader  # type: ignore[attr-defined]
    return module


def _fake_bs4() -> types.ModuleType:
    import re

    module = types.ModuleType("bs4")

    class _Tag:
        def __init__(self, text: str) -> None:
            self.string = text

        def decompose(self) -> None:
            return None

    class _Soup:
        def __init__(self, markup: object, _parser: str) -> None:
            text = markup.decode("utf-8") if isinstance(markup, (bytes, bytearray)) else str(markup)
            stripped = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.S | re.I)
            self._text = re.sub(r"<[^>]+>", "\n", stripped)
            found = re.search(r"<title>(.*?)</title>", text, flags=re.S | re.I)
            self.title = _Tag(found.group(1)) if found else None

        def __call__(self, _names: list[str]) -> list[_Tag]:
            return []

        def get_text(self, separator: str = "\n") -> str:
            parts = [p.strip() for p in self._text.split("\n") if p.strip()]
            return separator.join(parts)

    module.BeautifulSoup = _Soup  # type: ignore[attr-defined]
    return module


def _fake_docx(paragraphs: list[str], *, raise_on_read: bool = False) -> types.ModuleType:
    module = types.ModuleType("docx")

    class _Para:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Document:
        def __init__(self, _stream: object) -> None:
            if raise_on_read:
                raise ValueError("bad docx")
            self.paragraphs = [_Para(text) for text in paragraphs]

    module.Document = _Document  # type: ignore[attr-defined]
    return module


class TestPdfLoader(unittest.IsolatedAsyncioTestCase):
    async def test_joins_page_text(self) -> None:
        with patch.dict(sys.modules, {"pypdf": _fake_pypdf(["one", "two"])}):
            doc = await PdfLoader().load(b"%PDF-1.4 ...")
        assert doc.text == "one\n\ntwo"
        assert doc.metadata["page_count"] == 2
        assert doc.metadata["content_type"] == "application/pdf"

    async def test_corrupt_pdf_raises_valueerror(self) -> None:
        with patch.dict(sys.modules, {"pypdf": _fake_pypdf([], raise_on_read=True)}):
            with self.assertRaisesRegex(ValueError, "could not parse PDF"):
                await PdfLoader().load(b"garbage")

    async def test_missing_backend_raises_friendly_error(self) -> None:
        with patch.dict(sys.modules, {"pypdf": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-agents\[pdf\]"):
                await PdfLoader().load(b"%PDF")

    async def test_non_bytes_raises_typeerror(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be bytes"):
            await PdfLoader().load("nope")  # type: ignore[arg-type]


class TestHtmlLoader(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_visible_text_and_title(self) -> None:
        html = (
            b"<html><head><title>T</title></head><body><p>Hello</p>"
            b"<script>ignore()</script></body></html>"
        )
        with patch.dict(sys.modules, {"bs4": _fake_bs4()}):
            doc = await HtmlLoader().load(html)
        assert "Hello" in doc.text
        assert "ignore" not in doc.text
        assert doc.metadata["title"] == "T"
        assert doc.metadata["content_type"] == "text/html"

    async def test_missing_title_omitted(self) -> None:
        with patch.dict(sys.modules, {"bs4": _fake_bs4()}):
            doc = await HtmlLoader().load(b"<p>hi</p>")
        assert "title" not in doc.metadata

    async def test_missing_backend_raises_friendly_error(self) -> None:
        with patch.dict(sys.modules, {"bs4": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-agents\[html\]"):
                await HtmlLoader().load(b"<p>x</p>")


class TestDocxLoader(unittest.IsolatedAsyncioTestCase):
    async def test_joins_paragraphs(self) -> None:
        with patch.dict(sys.modules, {"docx": _fake_docx(["Hello", "World"])}):
            doc = await DocxLoader().load(b"PK\x03\x04 ...")
        assert doc.text == "Hello\nWorld"
        assert doc.metadata["paragraph_count"] == 2

    async def test_corrupt_docx_raises_valueerror(self) -> None:
        with patch.dict(sys.modules, {"docx": _fake_docx([], raise_on_read=True)}):
            with self.assertRaisesRegex(ValueError, "could not parse .docx"):
                await DocxLoader().load(b"garbage")

    async def test_missing_backend_raises_friendly_error(self) -> None:
        with patch.dict(sys.modules, {"docx": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-agents\[docx\]"):
                await DocxLoader().load(b"PK")


if __name__ == "__main__":
    unittest.main()
