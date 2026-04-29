"""Real-backend tests for RayDispatcher.

Uses a local Ray instance (``ray.init()``). Skips if ``ray`` is not
installed. Ray has heavy startup cost; tests are kept minimal.
"""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.needs_ray


@pytest.fixture(scope="module")
def ray_runtime():
    ray = pytest.importorskip("ray")
    ray.init(ignore_reinit_error=True, num_cpus=2)
    yield ray
    ray.shutdown()


@knot
async def _double(x: int) -> int:
    return x * 2


async def test_ray_dispatcher_runs_pipeline(ray_runtime):
    from pirn.engine.dispatchers.ray_dispatcher import RayDispatcher

    dispatcher = RayDispatcher(ray_module=ray_runtime)
    with Tapestry(dispatcher=dispatcher) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest(parameters={"x": 6}))
    assert result.succeeded
    assert result.outputs["d"] == 12


async def test_ray_dispatcher_result_has_correct_dispatcher_name(ray_runtime):
    from pirn.engine.dispatchers.ray_dispatcher import RayDispatcher

    dispatcher = RayDispatcher(ray_module=ray_runtime)
    with Tapestry(dispatcher=dispatcher) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest(parameters={"x": 1}))
    dispatchers = {rec.dispatcher for rec in result.lineage}
    assert "RayDispatcher" in dispatchers
