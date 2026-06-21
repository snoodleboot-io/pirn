"""Unit tests for :class:`ScadaDatabaseAssembler`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_oilgas.assemblers.scada_database_assembler import ScadaDatabaseAssembler
from pirn_oilgas.types.scada_payload import ScadaPayload


def _rows_param() -> Parameter:
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make() -> ScadaDatabaseAssembler:
    return ScadaDatabaseAssembler(
        rows=_rows_param(),
        tag="PUMP-01",
        since=datetime(2024, 1, 1, tzinfo=UTC),
        sample_interval_sec=1.0,
        _config=KnotConfig(id="assembler"),
    )


_SINCE = datetime(2024, 1, 1, tzinfo=UTC)
_ROWS = [(datetime(2024, 1, 1, 0, 0, i, tzinfo=UTC), float(i)) for i in range(5)]


class TestScadaDatabaseAssembler(unittest.IsolatedAsyncioTestCase):

    async def test_returns_scada_payload(self) -> None:
        knot = _make()
        result = await knot.process(rows=_ROWS, tag="PUMP-01", since=_SINCE, sample_interval_sec=1.0)
        assert isinstance(result, ScadaPayload)

    async def test_metadata_sensor_id_matches(self) -> None:
        knot = _make()
        result = await knot.process(rows=_ROWS, tag="PUMP-01", since=_SINCE, sample_interval_sec=1.0)
        assert result.series.sensor_id == "PUMP-01"

    async def test_sample_count_matches_rows(self) -> None:
        knot = _make()
        result = await knot.process(rows=_ROWS, tag="PUMP-01", since=_SINCE, sample_interval_sec=1.0)
        assert result.series.sample_count == 5

    async def test_values_array_shape(self) -> None:
        knot = _make()
        result = await knot.process(rows=_ROWS, tag="PUMP-01", since=_SINCE, sample_interval_sec=1.0)
        assert result.values.shape == (5,)

    async def test_rejects_non_list_rows(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="rows must be list"):
            await knot.process(rows="not-a-list", tag="PUMP-01", since=_SINCE, sample_interval_sec=1.0)  # type: ignore[arg-type]

    async def test_rejects_non_str_tag(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="tag must be str"):
            await knot.process(rows=_ROWS, tag=123, since=_SINCE, sample_interval_sec=1.0)  # type: ignore[arg-type]

    async def test_rejects_empty_tag(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="tag must be non-empty"):
            await knot.process(rows=_ROWS, tag="", since=_SINCE, sample_interval_sec=1.0)

    async def test_rejects_non_datetime_since(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="since must be datetime"):
            await knot.process(rows=_ROWS, tag="PUMP-01", since="2024-01-01", sample_interval_sec=1.0)  # type: ignore[arg-type]

    async def test_rejects_non_positive_interval(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="sample_interval_sec must be positive"):
            await knot.process(rows=_ROWS, tag="PUMP-01", since=_SINCE, sample_interval_sec=0.0)
