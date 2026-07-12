"""Tests for the stdlib-only loaders (F25-S1): Markdown, code, CSV, JSON.

These loaders need no optional backend, so they are exercised directly with
in-memory byte fixtures — happy path, malformed/edge-case inputs, and the shared
non-bytes type guard.
"""

from __future__ import annotations

import unittest

from pirn_agents.specializations.document_processing.loaders.code_loader import CodeLoader
from pirn_agents.specializations.document_processing.loaders.csv_loader import CsvLoader
from pirn_agents.specializations.document_processing.loaders.json_loader import JsonLoader
from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.markdown_loader import (
    MarkdownLoader,
)


class TestMarkdownLoader(unittest.IsolatedAsyncioTestCase):
    async def test_strips_formatting_and_keeps_raw(self) -> None:
        doc = await MarkdownLoader().load(b"# Heading\n\nSome **bold** [text](http://e).")
        assert isinstance(doc, LoadedDocument)
        assert "Heading" in doc.text
        assert "**" not in doc.text
        assert "bold" in doc.text
        assert "text" in doc.text and "http://e" not in doc.text
        assert doc.metadata["raw"].startswith("# Heading")
        assert doc.metadata["content_type"] == "text/markdown"

    async def test_can_preserve_raw_markdown(self) -> None:
        doc = await MarkdownLoader(strip_formatting=False).load(b"# Heading")
        assert doc.text == "# Heading"

    async def test_empty_input_yields_empty_text(self) -> None:
        doc = await MarkdownLoader().load(b"")
        assert doc.text == ""

    async def test_invalid_utf8_raises_valueerror(self) -> None:
        with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
            await MarkdownLoader().load(b"\xff\xfe")

    async def test_source_id_recorded(self) -> None:
        doc = await MarkdownLoader().load(b"x", source_id="doc-1")
        assert doc.source_id == "doc-1"


class TestCodeLoader(unittest.IsolatedAsyncioTestCase):
    async def test_preserves_source_verbatim(self) -> None:
        src = b"def f():\n    return 1\n"
        doc = await CodeLoader(language="python").load(src)
        assert doc.text == src.decode("utf-8")
        assert doc.metadata["language"] == "python"
        assert doc.metadata["line_count"] == 3

    async def test_language_omitted_when_not_given(self) -> None:
        doc = await CodeLoader().load(b"x = 1")
        assert "language" not in doc.metadata

    async def test_empty_input_line_count_zero(self) -> None:
        doc = await CodeLoader().load(b"")
        assert doc.text == ""
        assert doc.metadata["line_count"] == 0

    async def test_invalid_utf8_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
            await CodeLoader().load(b"\xff")


class TestCsvLoader(unittest.IsolatedAsyncioTestCase):
    async def test_parses_rows_into_records(self) -> None:
        doc = await CsvLoader().load(b"a,b\n1,2\n3,4\n")
        assert doc.records == ({"a": "1", "b": "2"}, {"a": "3", "b": "4"})
        assert doc.metadata["row_count"] == 2
        assert "a=1" in doc.text

    async def test_custom_delimiter(self) -> None:
        doc = await CsvLoader(delimiter=";").load(b"a;b\n1;2\n")
        assert doc.records == ({"a": "1", "b": "2"},)

    async def test_header_only_yields_no_records(self) -> None:
        doc = await CsvLoader().load(b"a,b\n")
        assert doc.records == ()
        assert doc.text == ""

    async def test_invalid_utf8_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
            await CsvLoader().load(b"\xff\xfe")


class TestJsonLoader(unittest.IsolatedAsyncioTestCase):
    async def test_array_of_objects_becomes_records(self) -> None:
        doc = await JsonLoader().load(b'[{"x": 1}, {"x": 2}]')
        assert doc.records == ({"x": 1}, {"x": 2})
        assert doc.metadata["record_count"] == 2

    async def test_scalar_array_elements_are_wrapped(self) -> None:
        doc = await JsonLoader().load(b"[1, 2]")
        assert doc.records == ({"value": 1}, {"value": 2})

    async def test_single_object_becomes_one_record(self) -> None:
        doc = await JsonLoader().load(b'{"a": 1}')
        assert doc.records == ({"a": 1},)

    async def test_scalar_top_level_wrapped(self) -> None:
        doc = await JsonLoader().load(b"42")
        assert doc.records == ({"value": 42},)

    async def test_malformed_json_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "could not parse JSON"):
            await JsonLoader().load(b"{not json}")

    async def test_non_bytes_raises_typeerror(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be bytes"):
            await JsonLoader().load("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
