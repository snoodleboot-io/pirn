"""Tests for :class:`TextTokenCounter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.feature_engineering.text_token_counter import (
    TextTokenCounter,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence_rows(self) -> None:
        with pytest.raises(TypeError, match="rows"):
            TextTokenCounter(
                rows="bad",  # type: ignore[arg-type]
                text_column="text",
                _config=KnotConfig(id="ttc"),
            )

    def test_rejects_empty_text_column(self) -> None:
        with pytest.raises(ValueError, match="text_column"):
            TextTokenCounter(
                rows=[],
                text_column="",
                _config=KnotConfig(id="ttc"),
            )

    def test_rejects_invalid_identifier(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            TextTokenCounter(
                rows=[],
                text_column="bad col",
                _config=KnotConfig(id="ttc"),
            )


@pytest.mark.asyncio
class TestBehaviour:
    async def test_whitespace_token_count(self) -> None:
        rows = [
            {"id": 1, "text": "hello world foo"},
            {"id": 2, "text": "one two"},
        ]
        with Tapestry() as t:
            TextTokenCounter(
                rows=rows,
                text_column="text",
                _config=KnotConfig(id="ttc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["ttc"]
        enriched = output["rows"]
        assert enriched[0]["token_count"] == 3
        assert enriched[1]["token_count"] == 2

    async def test_custom_output_column(self) -> None:
        rows = [{"id": 1, "body": "a b c d"}]
        with Tapestry() as t:
            TextTokenCounter(
                rows=rows,
                text_column="body",
                output_column="n_tokens",
                _config=KnotConfig(id="ttc2"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["ttc2"]["rows"][0]["n_tokens"] == 4

    async def test_preserves_existing_keys(self) -> None:
        rows = [{"id": 99, "text": "one two three"}]
        with Tapestry() as t:
            TextTokenCounter(
                rows=rows,
                text_column="text",
                _config=KnotConfig(id="ttc3"),
            )
        result = await t.run(RunRequest())
        enriched = result.outputs["ttc3"]["rows"][0]
        assert enriched["id"] == 99

    async def test_none_text_treated_as_empty(self) -> None:
        rows = [{"id": 1, "text": None}]
        with Tapestry() as t:
            TextTokenCounter(
                rows=rows,
                text_column="text",
                _config=KnotConfig(id="ttc4"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ttc4"]["rows"][0]["token_count"] == 0

    async def test_tokenizer_key_present(self) -> None:
        rows = [{"text": "hello"}]
        with Tapestry() as t:
            TextTokenCounter(
                rows=rows,
                text_column="text",
                _config=KnotConfig(id="ttc5"),
            )
        result = await t.run(RunRequest())
        assert "tokenizer" in result.outputs["ttc5"]
