"""Tests for :class:`ColumnHasher`."""

from __future__ import annotations

import hashlib
import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.feature_engineering.column_hasher import ColumnHasher
from pirn.tapestry import Tapestry


def _make_knot(**overrides: Any) -> ColumnHasher:
    defaults: dict[str, Any] = {
        "columns": ("email",),
        "algorithm": "sha256",
    }
    defaults.update(overrides)
    return ColumnHasher(rows=[], **defaults, _config=KnotConfig(id="hasher"))


class TestColumnHasher(unittest.IsolatedAsyncioTestCase):
    async def test_sha256_produces_64_char_hex(self) -> None:
        rows = [{"email": "alice@example.com"}]
        k = _make_knot()
        result = await k.process(rows=rows, columns=("email",), algorithm="sha256")
        assert len(result[0]["email"]) == 64

    async def test_md5_produces_32_char_hex(self) -> None:
        rows = [{"email": "alice@example.com"}]
        k = _make_knot(algorithm="md5")
        result = await k.process(rows=rows, columns=("email",), algorithm="md5")
        assert len(result[0]["email"]) == 32

    async def test_hash_is_deterministic(self) -> None:
        rows = [{"email": "alice@example.com"}]
        k = _make_knot()
        r1 = await k.process(rows=rows, columns=("email",), algorithm="sha256")
        r2 = await k.process(rows=rows, columns=("email",), algorithm="sha256")
        assert r1[0]["email"] == r2[0]["email"]

    async def test_hash_matches_expected(self) -> None:
        val = "alice@example.com"
        expected = hashlib.sha256(val.encode()).hexdigest()
        rows = [{"email": val}]
        k = _make_knot()
        result = await k.process(rows=rows, columns=("email",), algorithm="sha256")
        assert result[0]["email"] == expected

    async def test_non_target_column_unchanged(self) -> None:
        rows = [{"email": "a@b.com", "name": "Alice"}]
        k = _make_knot()
        result = await k.process(rows=rows, columns=("email",), algorithm="sha256")
        assert result[0]["name"] == "Alice"

    async def test_multiple_columns_hashed(self) -> None:
        rows = [{"email": "a@b.com", "phone": "123"}]
        k = _make_knot(columns=("email", "phone"))
        result = await k.process(rows=rows, columns=("email", "phone"), algorithm="sha256")
        assert len(result[0]["email"]) == 64
        assert len(result[0]["phone"]) == 64

    async def test_empty_input(self) -> None:
        k = _make_knot()
        result = await k.process(rows=[], columns=("email",), algorithm="sha256")
        assert result == []

    async def test_tapestry_run(self) -> None:
        rows = [{"email": "a@b.com"}]
        with Tapestry() as t:
            ColumnHasher(
                rows=rows, columns=("email",), algorithm="sha256",
                _config=KnotConfig(id="h"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [{"email": "a@b.com"}]

        with Tapestry() as t:
            rows_knot = emit_rows(_config=KnotConfig(id="rows"))
            ColumnHasher(
                rows=rows_knot,
                columns=("email",),
                algorithm="sha256",
                _config=KnotConfig(id="hasher"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs["hasher"][0]["email"]) == 64


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> ColumnHasher:
        defaults: dict[str, Any] = {
            "columns": ("email",),
            "algorithm": "sha256",
        }
        defaults.update(kwargs)
        with Tapestry():
            return ColumnHasher(rows=[], **defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ColumnHasher, **overrides: Any) -> Any:
        args: dict[str, Any] = {
            "rows": [{"email": "a@b.com"}],
            "columns": ("email",),
            "algorithm": "sha256",
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_invalid_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, columns=("bad col",))

    async def test_rejects_invalid_algorithm(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "algorithm"):
            await self._call(k, algorithm="sha512")
