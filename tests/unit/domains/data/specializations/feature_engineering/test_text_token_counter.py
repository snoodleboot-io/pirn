"""Tests for :class:`TextTokenCounter`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.feature_engineering.text_token_counter import (
    TextTokenCounter,
)
from pirn.tapestry import Tapestry


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
        @knot
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
