"""Tests for :class:`DaskFilter`."""

from __future__ import annotations

import dask.dataframe as dd
import pandas as pd
import pytest

pytestmark = pytest.mark.slow

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_filter import DaskFilter
from pirn.domains.data.lazy.dask.dask_source import DaskSource
from pirn.tapestry import Tapestry


def _orders_factory() -> dd.DataFrame:
    pdf = pd.DataFrame(
        {
            "id":     [1, 2, 3, 4],
            "amount": [10.0, 25.0, 5.0, 100.0],
            "region": ["EU", "EU", "EU", "US"],
        }
    )
    return dd.from_pandas(pdf, npartitions=2)


@pytest.mark.asyncio
async def test_filter_keeps_frame_deferred() -> None:
    with Tapestry() as t:
        src = DaskSource(
            factory=_orders_factory,
            backend_name="dask",
            _config=KnotConfig(id="src"),
        )
        DaskFilter(
            batch=src,
            predicate=lambda frame: frame.region == "EU",
            _config=KnotConfig(id="eu"),
        )
    result = await t.run(RunRequest())
    out: DaskDataFrame = result.outputs["eu"]
    # Still deferred — no compute yet.
    assert isinstance(out.frame, dd.DataFrame)
    # Materialise here in the test only to verify the predicate worked.
    rows = out.frame.compute()
    assert len(rows) == 3
    assert set(rows["region"].tolist()) == {"EU"}


@pytest.mark.asyncio
async def test_filter_chains() -> None:
    with Tapestry() as t:
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="src"))
        active = DaskFilter(
            batch=src,
            predicate=lambda frame: frame.region == "EU",
            _config=KnotConfig(id="eu"),
        )
        DaskFilter(
            batch=active,
            predicate=lambda frame: frame.amount > 5.0,
            _config=KnotConfig(id="big_eu"),
        )
    result = await t.run(RunRequest())
    out: DaskDataFrame = result.outputs["big_eu"]
    rows = out.frame.compute()
    assert len(rows) == 2  # ids 1, 2


def test_construct_rejects_non_callable_predicate() -> None:
    with Tapestry():
        src = DaskSource(factory=_orders_factory, _config=KnotConfig(id="s"))
        with pytest.raises(TypeError, match="callable"):
            DaskFilter(
                batch=src,
                predicate="region == 'EU'",  # type: ignore[arg-type]
                _config=KnotConfig(id="f"),
            )
