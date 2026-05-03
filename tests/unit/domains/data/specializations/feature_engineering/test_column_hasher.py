"""Tests for :class:`ColumnHasher`."""

from __future__ import annotations

import hashlib

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.feature_engineering.column_hasher import (
    ColumnHasher,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(**kwargs):
    with Tapestry():
        knot = ColumnHasher(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="hasher"),
        )
    return knot


class TestConstruction:
    def test_rejects_invalid_column(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make(columns=["bad col"])

    def test_rejects_invalid_algorithm(self) -> None:
        with pytest.raises(ValueError, match="algorithm"):
            _make(columns=["email"], algorithm="sha512")


@pytest.mark.asyncio
class TestBehaviour:
    async def test_sha256_produces_64_char_hex(self) -> None:
        rows = [{"email": "alice@example.com"}]
        knot = _make(columns=["email"], algorithm="sha256")
        result = await knot.process(rows=rows)
        assert len(result[0]["email"]) == 64

    async def test_md5_produces_32_char_hex(self) -> None:
        rows = [{"email": "alice@example.com"}]
        knot = _make(columns=["email"], algorithm="md5")
        result = await knot.process(rows=rows)
        assert len(result[0]["email"]) == 32

    async def test_hash_is_deterministic(self) -> None:
        rows = [{"email": "alice@example.com"}]
        knot = _make(columns=["email"])
        r1 = await knot.process(rows=rows)
        r2 = await knot.process(rows=rows)
        assert r1[0]["email"] == r2[0]["email"]

    async def test_hash_matches_expected(self) -> None:
        val = "alice@example.com"
        expected = hashlib.sha256(val.encode()).hexdigest()
        rows = [{"email": val}]
        knot = _make(columns=["email"])
        result = await knot.process(rows=rows)
        assert result[0]["email"] == expected

    async def test_non_target_column_unchanged(self) -> None:
        rows = [{"email": "a@b.com", "name": "Alice"}]
        knot = _make(columns=["email"])
        result = await knot.process(rows=rows)
        assert result[0]["name"] == "Alice"

    async def test_multiple_columns_hashed(self) -> None:
        rows = [{"email": "a@b.com", "phone": "123"}]
        knot = _make(columns=["email", "phone"])
        result = await knot.process(rows=rows)
        assert len(result[0]["email"]) == 64
        assert len(result[0]["phone"]) == 64

    async def test_empty_input(self) -> None:
        knot = _make(columns=["email"])
        result = await knot.process(rows=[])
        assert result == []
