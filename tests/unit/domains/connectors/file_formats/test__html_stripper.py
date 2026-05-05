"""Tests for :class:`_HtmlStripper`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.file_formats._html_stripper import _HtmlStripper


class TestHtmlStripper(unittest.TestCase):
    def _strip(self, html: str) -> str:
        s = _HtmlStripper()
        s.feed(html)
        return s.text()

    def test_plain_text_unchanged(self) -> None:
        result = self._strip("hello world")
        self.assertEqual(result, "hello world")

    def test_strips_inline_tags(self) -> None:
        result = self._strip("<b>bold</b> text")
        self.assertIn("bold", result)
        self.assertIn("text", result)

    def test_block_tags_add_newlines(self) -> None:
        result = self._strip("<p>first</p><p>second</p>")
        lines = result.splitlines()
        self.assertGreater(len(lines), 1)
        full = " ".join(lines)
        self.assertIn("first", full)
        self.assertIn("second", full)

    def test_empty_string(self) -> None:
        result = self._strip("")
        self.assertEqual(result, "")

    def test_nested_tags(self) -> None:
        result = self._strip("<div><p>nested</p></div>")
        self.assertIn("nested", result)
