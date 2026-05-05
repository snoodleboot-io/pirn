"""Tests for :class:`StringNormalizer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.feature_engineering.string_normalizer import (
    StringNormalizer,
)
from pirn.tapestry import Tapestry


def _make_knot(**overrides: Any) -> StringNormalizer:
    defaults: dict[str, Any] = {
        "columns": ("name",),
        "lowercase": True,
        "strip": True,
        "remove_punctuation": False,
        "unicode_form": "NFC",
    }
    defaults.update(overrides)
    return StringNormalizer(rows=[], **defaults, _config=KnotConfig(id="normalizer"))


def _call_args(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "columns": ("name",),
        "lowercase": True,
        "strip": True,
        "remove_punctuation": False,
        "unicode_form": "NFC",
    }
    defaults.update(overrides)
    return defaults


class TestStringNormalizer(unittest.IsolatedAsyncioTestCase):
    async def test_lowercase(self) -> None:
        rows = [{"name": "ALICE"}]
        opts = {
            "lowercase": True, "strip": False,
            "remove_punctuation": False, "unicode_form": "none",
        }
        k = _make_knot(**opts)
        result = await k.process(rows=rows, **_call_args(**opts))
        assert result[0]["name"] == "alice"

    async def test_strip(self) -> None:
        rows = [{"name": "  Alice  "}]
        opts = {
            "lowercase": False, "strip": True,
            "remove_punctuation": False, "unicode_form": "none",
        }
        k = _make_knot(**opts)
        result = await k.process(rows=rows, **_call_args(**opts))
        assert result[0]["name"] == "Alice"

    async def test_remove_punctuation(self) -> None:
        rows = [{"name": "Hello, World!"}]
        opts = {
            "lowercase": False, "strip": False,
            "remove_punctuation": True, "unicode_form": "none",
        }
        k = _make_knot(**opts)
        result = await k.process(rows=rows, **_call_args(**opts))
        assert "," not in result[0]["name"]
        assert "!" not in result[0]["name"]

    async def test_non_string_value_left_intact(self) -> None:
        rows = [{"score": 99}]
        k = _make_knot(columns=("score",))
        result = await k.process(rows=rows, **_call_args(columns=("score",)))
        assert result[0]["score"] == 99

    async def test_non_target_column_unchanged(self) -> None:
        rows = [{"name": "ALICE", "age": 30}]
        k = _make_knot()
        result = await k.process(rows=rows, **_call_args())
        assert result[0]["age"] == 30

    async def test_unicode_normalise_nfc(self) -> None:
        nfd = "À"
        rows = [{"name": nfd}]
        opts = {
            "lowercase": False, "strip": False,
            "remove_punctuation": False, "unicode_form": "NFC",
        }
        k = _make_knot(**opts)
        result = await k.process(rows=rows, **_call_args(**opts))
        assert len(result[0]["name"]) == 1

    async def test_empty_input(self) -> None:
        k = _make_knot()
        result = await k.process(rows=[], **_call_args())
        assert result == []

    async def test_tapestry_run(self) -> None:
        rows = [{"name": "ALICE"}]
        with Tapestry() as t:
            StringNormalizer(
                rows=rows,
                columns=("name",),
                lowercase=True,
                strip=True,
                remove_punctuation=False,
                unicode_form="NFC",
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [{"name": "ALICE"}]

        with Tapestry() as t:
            rows_knot = emit_rows(_config=KnotConfig(id="rows"))
            StringNormalizer(
                rows=rows_knot,
                columns=("name",),
                lowercase=True,
                strip=True,
                remove_punctuation=False,
                unicode_form="NFC",
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["n"][0]["name"] == "alice"


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> StringNormalizer:
        defaults: dict[str, Any] = {
            "columns": ("name",),
            "lowercase": True,
            "strip": True,
            "remove_punctuation": False,
            "unicode_form": "NFC",
        }
        defaults.update(kwargs)
        with Tapestry():
            return StringNormalizer(rows=[], **defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: StringNormalizer, **overrides: Any) -> Any:
        args = _call_args(**overrides)
        return await k.process(rows=[{"name": "test"}], **args)

    async def test_rejects_invalid_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, columns=("bad col",))

    async def test_rejects_invalid_unicode_form(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "unicode_form"):
            await self._call(k, unicode_form="XYZ")
