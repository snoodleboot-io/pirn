"""Tests for :class:`DaskJoin`."""

from __future__ import annotations

import dask.dataframe as dd
import pandas as pd
import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_join import DaskJoin
from pirn.domains.data.lazy.dask.dask_source import DaskSource
from pirn.tapestry import Tapestry


def _users_factory() -> dd.DataFrame:
    pdf = pd.DataFrame(
        {"user_id": [1, 2, 3], "name": ["alice", "bob", "carol"]}
    )
    return dd.from_pandas(pdf, npartitions=1)


def _orders_factory() -> dd.DataFrame:
    pdf = pd.DataFrame(
        {"user_id": [1, 1, 2, 4], "amount": [10.0, 20.0, 30.0, 40.0]}
    )
    return dd.from_pandas(pdf, npartitions=2)


@pytest.mark.asyncio
async def test_inner_join_on_shared_column() -> None:
    with Tapestry() as t:
        users = DaskSource(factory=_users_factory, _config=KnotConfig(id="users"))
        orders = DaskSource(
            factory=_orders_factory, _config=KnotConfig(id="orders")
        )
        DaskJoin(
            left=users, right=orders, on="user_id", how="inner",
            _config=KnotConfig(id="joined"),
        )
    result = await t.run(RunRequest())
    out: DaskDataFrame = result.outputs["joined"]
    rows = out.frame.compute()
    assert len(rows) == 3   # alice has 2, bob has 1, carol has 0


@pytest.mark.asyncio
async def test_left_join_keeps_unmatched() -> None:
    with Tapestry() as t:
        users = DaskSource(factory=_users_factory, _config=KnotConfig(id="users"))
        orders = DaskSource(
            factory=_orders_factory, _config=KnotConfig(id="orders")
        )
        DaskJoin(
            left=users, right=orders, on="user_id", how="left",
            _config=KnotConfig(id="joined"),
        )
    result = await t.run(RunRequest())
    out: DaskDataFrame = result.outputs["joined"]
    rows = out.frame.compute()
    assert "carol" in rows["name"].tolist()


@pytest.mark.asyncio
async def test_left_on_right_on() -> None:
    with Tapestry() as t:
        users = DaskSource(factory=_users_factory, _config=KnotConfig(id="users"))
        orders = DaskSource(
            factory=_orders_factory, _config=KnotConfig(id="orders")
        )
        DaskJoin(
            left=users, right=orders,
            left_on="user_id", right_on="user_id", how="inner",
            _config=KnotConfig(id="joined"),
        )
    result = await t.run(RunRequest())
    out: DaskDataFrame = result.outputs["joined"]
    rows = out.frame.compute()
    assert len(rows) == 3


def test_construct_rejects_unknown_how() -> None:
    with Tapestry():
        u = DaskSource(factory=_users_factory, _config=KnotConfig(id="u"))
        o = DaskSource(factory=_orders_factory, _config=KnotConfig(id="o"))
        with pytest.raises(ValueError, match="how must be one of"):
            DaskJoin(
                left=u, right=o, on="user_id", how="diagonal",
                _config=KnotConfig(id="j"),
            )


def test_construct_rejects_missing_keys() -> None:
    with Tapestry():
        u = DaskSource(factory=_users_factory, _config=KnotConfig(id="u"))
        o = DaskSource(factory=_orders_factory, _config=KnotConfig(id="o"))
        with pytest.raises(TypeError, match="must supply on"):
            DaskJoin(left=u, right=o, how="inner", _config=KnotConfig(id="j"))


def test_construct_rejects_on_with_left_on() -> None:
    with Tapestry():
        u = DaskSource(factory=_users_factory, _config=KnotConfig(id="u"))
        o = DaskSource(factory=_orders_factory, _config=KnotConfig(id="o"))
        with pytest.raises(TypeError, match="mutually exclusive"):
            DaskJoin(
                left=u, right=o,
                on="user_id", left_on="user_id", right_on="user_id",
                how="inner", _config=KnotConfig(id="j"),
            )
