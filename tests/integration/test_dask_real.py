"""Real-backend tests for DaskDispatcher.

Uses an in-process ``LocalCluster`` — no Docker required. Skips if
``dask.distributed`` is not installed.
"""

from __future__ import annotations

import pytest

from pirn import KnotConfig, Parameter, RunRequest, Tapestry, knot

pytestmark = pytest.mark.needs_dask


@pytest.fixture(scope="module")
async def dask_client():
    pytest.importorskip("dask.distributed")
    from dask.distributed import Client, LocalCluster

    cluster = LocalCluster(n_workers=2, threads_per_worker=1, asynchronous=True)
    await cluster
    client = await Client(cluster, asynchronous=True)
    yield client
    await client.close()
    await cluster.close()


@knot
async def _double(x: int) -> int:
    return x * 2


@knot
async def _add(x: int, y: int) -> int:
    return x + y


async def test_dask_dispatcher_runs_single_knot(dask_client):
    from pirn.engine.dask_dispatcher import DaskDispatcher

    dispatcher = DaskDispatcher(client=dask_client)
    with Tapestry(dispatcher=dispatcher) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest(parameters={"x": 5}))
    assert result.succeeded
    assert result.outputs["d"] == 10


async def test_dask_dispatcher_runs_multi_knot_pipeline(dask_client):
    from pirn.engine.dask_dispatcher import DaskDispatcher

    dispatcher = DaskDispatcher(client=dask_client)
    with Tapestry(dispatcher=dispatcher) as t:
        x = Parameter("x", int, _config=KnotConfig(id="x"))
        y = Parameter("y", int, _config=KnotConfig(id="y"))
        _add(x=x, y=y, _config=KnotConfig(id="sum"))

    result = await t.run(RunRequest(parameters={"x": 3, "y": 7}))
    assert result.succeeded
    assert result.outputs["sum"] == 10


async def test_dask_dispatcher_result_has_correct_dispatcher_name(dask_client):
    from pirn.engine.dask_dispatcher import DaskDispatcher

    dispatcher = DaskDispatcher(client=dask_client)
    with Tapestry(dispatcher=dispatcher) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest(parameters={"x": 1}))
    dispatchers = {rec.dispatcher for rec in result.lineage}
    assert "DaskDispatcher" in dispatchers
