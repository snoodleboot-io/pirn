"""Tests for :class:`StringNormalizer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.feature_engineering.string_normalizer import (
    StringNormalizer,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(**kwargs):
    with Tapestry():
        knot = StringNormalizer(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="normalizer"),
        )
    return knot


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_column(self) -> None:
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            _make(columns=["bad col"])

    def test_rejects_invalid_unicode_form(self) -> None:
        with self.assertRaisesRegex(ValueError, "unicode_form"):
            _make(columns=["name"], unicode_form="XYZ")


class TestBehaviour(unittest.IsolatedAsyncioTestCase):
    async def test_lowercase(self) -> None:
        rows = [{"name": "ALICE"}]
        knot = _make(columns=["name"], lowercase=True, strip=False, remove_punctuation=False, unicode_form="none")
        result = await knot.process(rows=rows)
        assert result[0]["name"] == "alice"

    async def test_strip(self) -> None:
        rows = [{"name": "  Alice  "}]
        knot = _make(columns=["name"], lowercase=False, strip=True, remove_punctuation=False, unicode_form="none")
        result = await knot.process(rows=rows)
        assert result[0]["name"] == "Alice"

    async def test_remove_punctuation(self) -> None:
        rows = [{"name": "Hello, World!"}]
        knot = _make(columns=["name"], lowercase=False, strip=False, remove_punctuation=True, unicode_form="none")
        result = await knot.process(rows=rows)
        assert "," not in result[0]["name"]
        assert "!" not in result[0]["name"]

    async def test_non_string_value_left_intact(self) -> None:
        rows = [{"score": 99}]
        knot = _make(columns=["score"], lowercase=True)
        result = await knot.process(rows=rows)
        assert result[0]["score"] == 99

    async def test_non_target_column_unchanged(self) -> None:
        rows = [{"name": "ALICE", "age": 30}]
        knot = _make(columns=["name"])
        result = await knot.process(rows=rows)
        assert result[0]["age"] == 30

    async def test_unicode_normalise_nfc(self) -> None:
        nfd = "À"
        rows = [{"name": nfd}]
        knot = _make(columns=["name"], lowercase=False, strip=False, remove_punctuation=False, unicode_form="NFC")
        result = await knot.process(rows=rows)
        assert len(result[0]["name"]) == 1

    async def test_empty_input(self) -> None:
        knot = _make(columns=["name"])
        result = await knot.process(rows=[])
        assert result == []
