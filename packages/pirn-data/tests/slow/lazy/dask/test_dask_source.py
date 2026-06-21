"""Tests for :class:`DaskSource`."""

from __future__ import annotations

import dask.dataframe as dd
import pandas as pd
import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn_data.lazy.dask.dask_source import DaskSource


def _users_factory() -> dd.DataFrame:
    pdf = pd.DataFrame({"id": [1, 2, 3], "name": ["alice", "bob", "carol"]})
    return dd.from_pandas(pdf, npartitions=1)


@pytest.mark.asyncio
async def test_dask_source_emits_deferred_frame() -> None:
    with Tapestry() as t:
        DaskSource(
            factory=_users_factory,
            backend_name="dask",
            _config=KnotConfig(id="users"),
        )
    result = await t.run(RunRequest())
    assert result.succeeded
    out: DaskDataFrame = result.outputs["users"]
    assert out.backend_name == "dask"
    assert set(out.column_names) == {"id", "name"}


@pytest.mark.asyncio
async def test_dask_source_path_with_reader(tmp_path) -> None:
    parquet_path = tmp_path / "users.parquet"
    pd.DataFrame(
        {"id": [1, 2], "name": ["alice", "bob"]}
    ).to_parquet(parquet_path)

    with Tapestry() as t:
        DaskSource(
            path=str(parquet_path),
            reader=dd.read_parquet,
            _config=KnotConfig(id="users"),
        )
    result = await t.run(RunRequest())
    assert result.succeeded
    out: DaskDataFrame = result.outputs["users"]
    assert set(out.column_names) == {"id", "name"}


def test_construct_rejects_neither_factory_nor_path() -> None:
    with pytest.raises(TypeError, match="factory or path"):
        DaskSource(_config=KnotConfig(id="x"))


def test_construct_rejects_both_factory_and_path() -> None:
    with pytest.raises(TypeError, match="mutually exclusive"):
        DaskSource(
            factory=_users_factory,
            path="/tmp/foo",
            reader=dd.read_parquet,
            _config=KnotConfig(id="x"),
        )


def test_construct_rejects_path_without_reader() -> None:
    with pytest.raises(TypeError, match="reader is required"):
        DaskSource(path="/tmp/foo", _config=KnotConfig(id="x"))


def test_construct_rejects_empty_path() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        DaskSource(path="", reader=dd.read_parquet, _config=KnotConfig(id="x"))


def test_construct_rejects_non_callable_factory() -> None:
    with pytest.raises(TypeError, match="callable"):
        DaskSource(factory="not callable", _config=KnotConfig(id="x"))  # type: ignore[arg-type]
