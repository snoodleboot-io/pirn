"""Tests for :class:`pirn.domains.data.transforms.cast.Cast`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.transforms.cast import Cast
from pirn.tapestry import Tapestry


@knot
async def emit_string_users() -> DataBatch:
    schema = DataSchema(columns={"id": str, "amount": str, "name": str})
    rows = (
        {"id": "1", "amount": "12.5",  "name": "alice"},
        {"id": "2", "amount": "99.99", "name": "bob"},
    )
    return DataBatch(rows=rows, schema=schema)


@knot
async def emit_with_null() -> DataBatch:
    rows = ({"id": "1", "amount": None},)
    return DataBatch(rows=rows)


@knot
async def emit_with_invalid() -> DataBatch:
    rows = ({"id": "not-an-int"},)
    return DataBatch(rows=rows)


@pytest.mark.asyncio
class TestCast:
    async def test_casts_values_per_column(self) -> None:
        with Tapestry() as t:
            batch = emit_string_users(_config=KnotConfig(id="users"))
            Cast(
                batch=batch,
                casts={"id": int, "amount": float},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["casted"]
        assert out.rows[0]["id"] == 1
        assert out.rows[0]["amount"] == 12.5
        assert out.rows[1]["id"] == 2

    async def test_updates_schema_to_target_types(self) -> None:
        with Tapestry() as t:
            batch = emit_string_users(_config=KnotConfig(id="users"))
            Cast(
                batch=batch,
                casts={"id": int, "amount": float},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["casted"]
        assert out.schema.columns["id"] is int
        assert out.schema.columns["amount"] is float

    async def test_none_passes_through_uncoerced(self) -> None:
        with Tapestry() as t:
            batch = emit_with_null(_config=KnotConfig(id="users"))
            Cast(
                batch=batch,
                casts={"amount": float},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: DataBatch = result.outputs["casted"]
        assert out.rows[0]["amount"] is None

    async def test_invalid_value_raises(self) -> None:
        with Tapestry() as t:
            batch = emit_with_invalid(_config=KnotConfig(id="users"))
            Cast(
                batch=batch,
                casts={"id": int},
                _config=KnotConfig(id="casted", validate_io=False),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
        assert any(
            "could not coerce" in (exc.message or "")
            for exc in result.exceptions
        )


class TestConstruction:
    def test_rejects_non_type_value(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="must be a type"):
                Cast(
                    batch=batch, casts={"a": "int"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="c"),
                )
