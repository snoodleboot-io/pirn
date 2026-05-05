"""Tests for :class:`pirn.domains.data.transforms.normalize.Normalize`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.transforms.normalize import Normalize
from pirn.domains.data.transforms.normalize_column_rule import NormalizeColumnRule
from pirn.tapestry import Tapestry


@knot
async def emit_messy() -> DataBatch:
    rows = (
        {"name": "  Alice   Smith  ",  "region": "EU",  "comment": "n/a"},
        {"name": "BOB",                 "region": "us",  "comment": ""},
        {"name": "carol",               "region": "Asia","comment": "needs review"},
    )
    return DataBatch(rows=rows)


def _make_batch() -> DataBatch:
    return DataBatch(rows=({"name": "  Alice  ", "region": "eu"},))


class TestNormalize(unittest.IsolatedAsyncioTestCase):
    async def test_strip_whitespace_collapses_runs(self) -> None:
        with Tapestry() as t:
            batch = emit_messy(_config=KnotConfig(id="batch"))
            Normalize(
                batch=batch,
                rules={"name": NormalizeColumnRule(strip_whitespace=True)},
                _config=KnotConfig(id="norm"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["norm"]
        assert out.rows[0]["name"] == "Alice Smith"

    async def test_case_normalisation(self) -> None:
        with Tapestry() as t:
            batch = emit_messy(_config=KnotConfig(id="batch"))
            Normalize(
                batch=batch,
                rules={"region": NormalizeColumnRule(case="upper")},
                _config=KnotConfig(id="norm"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["norm"]
        assert tuple(r["region"] for r in out.rows) == ("EU", "US", "ASIA")

    async def test_null_tokens_replace_value_with_none(self) -> None:
        with Tapestry() as t:
            batch = emit_messy(_config=KnotConfig(id="batch"))
            Normalize(
                batch=batch,
                rules={
                    "comment": NormalizeColumnRule(
                        null_tokens=("", "n/a", "na"),
                    )
                },
                _config=KnotConfig(id="norm"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["norm"]
        assert out.rows[0]["comment"] is None  # "n/a"
        assert out.rows[1]["comment"] is None  # ""
        assert out.rows[2]["comment"] == "needs review"

    async def test_combined_rules_apply_in_order(self) -> None:
        with Tapestry() as t:
            batch = emit_messy(_config=KnotConfig(id="batch"))
            Normalize(
                batch=batch,
                rules={
                    "name": NormalizeColumnRule(
                        strip_whitespace=True, case="title",
                    ),
                },
                _config=KnotConfig(id="norm"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["norm"]
        assert out.rows[0]["name"] == "Alice Smith"
        assert out.rows[1]["name"] == "Bob"

    async def test_non_string_values_unchanged(self) -> None:
        @knot
        async def numbers() -> DataBatch:
            return DataBatch(rows=({"id": 1, "name": " alice "},))

        with Tapestry() as t:
            batch = numbers(_config=KnotConfig(id="batch"))
            Normalize(
                batch=batch,
                rules={
                    "id":   NormalizeColumnRule(strip_whitespace=True),
                    "name": NormalizeColumnRule(strip_whitespace=True),
                },
                _config=KnotConfig(id="norm"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["norm"]
        assert out.rows[0]["id"] == 1
        assert out.rows[0]["name"] == "alice"


class TestNormalizeColumnRule(unittest.TestCase):
    def test_rejects_invalid_case_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be one of"):
            NormalizeColumnRule(case="random")

    def test_accepts_none_case(self) -> None:
        # No raise.
        NormalizeColumnRule(case=None)


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rules_from_upstream_knot(self) -> None:
        @knot
        async def emit_rules() -> dict:
            return {"name": NormalizeColumnRule(strip_whitespace=True)}

        with Tapestry() as t:
            batch = emit_messy(_config=KnotConfig(id="batch"))
            rules_knot = emit_rules(_config=KnotConfig(id="rules"))
            Normalize(
                batch=batch,
                rules=rules_knot,
                _config=KnotConfig(id="norm"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["norm"]
        assert out.rows[0]["name"] == "Alice Smith"


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self) -> Normalize:
        @knot
        async def upstream() -> DataBatch:
            return _make_batch()

        with Tapestry():
            batch = upstream(_config=KnotConfig(id="up"))
            return Normalize(
                batch=batch,
                rules={"name": NormalizeColumnRule(strip_whitespace=True)},
                _config=KnotConfig(id="n"),
            )

    async def test_rejects_empty_rules(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=_make_batch(), rules={})

    async def test_rejects_non_rule_value(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "NormalizeColumnRule"):
            await k.process(
                batch=_make_batch(),
                rules={"name": "lower"},  # type: ignore[arg-type]
            )

    async def test_rejects_empty_key(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty strings"):
            await k.process(
                batch=_make_batch(),
                rules={"": NormalizeColumnRule(strip_whitespace=True)},
            )
