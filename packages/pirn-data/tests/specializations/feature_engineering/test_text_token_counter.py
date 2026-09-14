"""Tests for :class:`TextTokenCounter`."""

from __future__ import annotations

import sys
import types
import unittest
from typing import Any
from unittest.mock import patch

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_data.specializations.feature_engineering.text_token_counter import (
    TextTokenCounter,
)

# tiktoken is an optional extra (``pirn-data[tiktoken]``) and fetches its BPE files
# over the network. Every test here pins whether it is importable: a ``None``
# entry in ``sys.modules`` makes the import fail, so the whitespace fallback is
# what the counts below exercise, whatever the environment has installed.
_no_tiktoken = patch.dict(sys.modules, {"tiktoken": None})


def setUpModule() -> None:
    _no_tiktoken.start()


def tearDownModule() -> None:
    _no_tiktoken.stop()


def _make_knot(**overrides: Any) -> TextTokenCounter:
    defaults: dict[str, Any] = {
        "rows": [],
        "text_column": "text",
        "output_column": "token_count",
        "tiktoken_encoding": "cl100k_base",
    }
    defaults.update(overrides)
    return TextTokenCounter(**defaults, _config=KnotConfig(id="ttc"))


class TestTextTokenCounter(unittest.IsolatedAsyncioTestCase):
    async def test_process_directly_with_plain_values(self) -> None:
        rows = [{"id": 1, "text": "hello world"}, {"id": 2, "text": "one"}]
        with Tapestry():
            k = TextTokenCounter(
                rows=rows,
                text_column="text",
                output_column="token_count",
                tiktoken_encoding="cl100k_base",
                _config=KnotConfig(id="ttc_direct"),
            )
        result = await k.process(
            rows=rows,
            text_column="text",
            output_column="token_count",
            tiktoken_encoding="cl100k_base",
        )
        assert result["succeeded"] is True
        assert result["rows"][0]["token_count"] == 2
        assert result["rows"][1]["token_count"] == 1
        assert "tokenizer" in result

    async def test_whitespace_token_count(self) -> None:
        rows = [
            {"id": 1, "text": "hello world foo"},
            {"id": 2, "text": "one two"},
        ]
        with Tapestry() as t:
            _make_knot(rows=rows)
        result = await t.run(RunRequest())
        assert result.succeeded
        enriched = result.outputs["ttc"]["rows"]
        assert enriched[0]["token_count"] == 3
        assert enriched[1]["token_count"] == 2

    async def test_custom_output_column(self) -> None:
        rows = [{"id": 1, "body": "a b c d"}]
        with Tapestry() as t:
            TextTokenCounter(
                rows=rows,
                text_column="body",
                output_column="n_tokens",
                tiktoken_encoding="cl100k_base",
                _config=KnotConfig(id="ttc2"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["ttc2"]["rows"][0]["n_tokens"] == 4

    async def test_preserves_existing_keys(self) -> None:
        rows = [{"id": 99, "text": "one two three"}]
        with Tapestry() as t:
            _make_knot(rows=rows)
        result = await t.run(RunRequest())
        enriched = result.outputs["ttc"]["rows"][0]
        assert enriched["id"] == 99

    async def test_none_text_treated_as_empty(self) -> None:
        rows = [{"id": 1, "text": None}]
        with Tapestry() as t:
            _make_knot(rows=rows)
        result = await t.run(RunRequest())
        assert result.outputs["ttc"]["rows"][0]["token_count"] == 0

    async def test_tokenizer_key_present(self) -> None:
        rows = [{"text": "hello"}]
        with Tapestry() as t:
            _make_knot(rows=rows)
        result = await t.run(RunRequest())
        assert "tokenizer" in result.outputs["ttc"]


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @KnotFactory.knot
        async def emit_rows() -> list:
            return [{"text": "one two three"}]

        with Tapestry() as t:
            rows_knot = emit_rows(_config=KnotConfig(id="rows"))
            TextTokenCounter(
                rows=rows_knot,
                text_column="text",
                output_column="token_count",
                tiktoken_encoding="cl100k_base",
                _config=KnotConfig(id="ttc"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ttc"]["rows"][0]["token_count"] == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> TextTokenCounter:
        defaults: dict[str, Any] = {
            "rows": [],
            "text_column": "text",
            "output_column": "token_count",
            "tiktoken_encoding": "cl100k_base",
        }
        defaults.update(kwargs)
        with Tapestry():
            return TextTokenCounter(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: TextTokenCounter, **overrides: Any) -> Any:
        args: dict[str, Any] = {
            "rows": [{"text": "hello"}],
            "text_column": "text",
            "output_column": "token_count",
            "tiktoken_encoding": "cl100k_base",
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_non_sequence_rows(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "rows"):
            await self._call(k, rows="bad")

    async def test_rejects_empty_text_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "text_column"):
            await self._call(k, text_column="")

    async def test_rejects_invalid_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, text_column="bad col")


class TestTokenizerSelection(unittest.IsolatedAsyncioTestCase):
    async def test_whitespace_fallback_when_tiktoken_is_absent(self) -> None:
        with Tapestry():
            k = _make_knot()
        result = await k.process(
            rows=[{"text": "a b"}],
            text_column="text",
            output_column="token_count",
            tiktoken_encoding="cl100k_base",
        )
        assert result["tokenizer"] == "whitespace"
        assert result["rows"][0]["token_count"] == 2

    async def test_uses_tiktoken_encoding_when_installed(self) -> None:
        fake = types.ModuleType("tiktoken")

        class _Encoding:
            def encode(self, text: str) -> list[int]:
                return list(range(len(text)))

        requested: list[str] = []

        def get_encoding(name: str) -> _Encoding:
            requested.append(name)
            return _Encoding()

        fake.get_encoding = get_encoding
        with Tapestry():
            k = _make_knot()
        with patch.dict(sys.modules, {"tiktoken": fake}):
            result = await k.process(
                rows=[{"text": "abcd"}],
                text_column="text",
                output_column="token_count",
                tiktoken_encoding="cl100k_base",
            )
        assert requested == ["cl100k_base"]
        assert result["tokenizer"] == "tiktoken:cl100k_base"
        assert result["rows"][0]["token_count"] == 4
