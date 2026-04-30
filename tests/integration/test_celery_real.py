"""Real-backend tests for CeleryDispatcher.

Requires a running Redis broker (shares the ValKey container from
docker-compose.test.yml) and spawns a Celery worker subprocess.
Gated by ``pytest.mark.needs_celery``.

Set ``PIRN_TEST_CELERY_BROKER`` (defaults to ``redis://localhost:6379/1``)
to run; skips silently when celery or redis is unavailable.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.needs_celery

_BROKER = os.environ.get("PIRN_TEST_CELERY_BROKER", "redis://localhost:6379/1")


@pytest.fixture(scope="module")
def celery_worker():
    """Spawn a Celery worker subprocess and tear it down after the module."""
    pytest.importorskip("celery")
    pytest.importorskip("redis")

    # Worker script: registers the pirn task and starts the worker.
    worker_script = """
import sys
from celery import Celery
from pirn.engine.dispatchers.celery_dispatcher import register_celery_worker_task

broker = sys.argv[1]
app = Celery("pirn_test", broker=broker, backend=broker)
app.conf.update(
    task_serializer="pickle",
    accept_content=["pickle"],
    result_serializer="pickle",
)
register_celery_worker_task(app)
worker = app.Worker(concurrency=2, loglevel="error")
worker.start()
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", worker_script, _BROKER],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Give the worker time to connect to the broker.
    time.sleep(3)
    yield proc
    proc.terminate()
    proc.wait(timeout=10)


@knot
async def _double(x: int) -> int:
    return x * 2


async def test_celery_dispatcher_runs_pipeline(celery_worker):
    from celery import Celery

    from pirn.engine.dispatchers.celery_dispatcher import register_celery_worker_task

    app = Celery("pirn_test", broker=_BROKER, backend=_BROKER)
    app.conf.update(
        task_serializer="pickle",
        accept_content=["pickle"],
        result_serializer="pickle",
    )
    register_celery_worker_task(app)

    from pirn.engine.dispatchers.celery_dispatcher import CeleryDispatcher

    dispatcher = CeleryDispatcher(app=app)
    with Tapestry(dispatcher=dispatcher) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest(parameters={"x": 4}))
    assert result.succeeded
    assert result.outputs["d"] == 8


async def test_celery_dispatcher_result_has_correct_dispatcher_name(celery_worker):
    from celery import Celery

    from pirn.engine.dispatchers.celery_dispatcher import (
        CeleryDispatcher,
        register_celery_worker_task,
    )

    app = Celery("pirn_test", broker=_BROKER, backend=_BROKER)
    app.conf.update(
        task_serializer="pickle",
        accept_content=["pickle"],
        result_serializer="pickle",
    )
    register_celery_worker_task(app)

    dispatcher = CeleryDispatcher(app=app)
    with Tapestry(dispatcher=dispatcher) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        _double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest(parameters={"x": 1}))
    dispatchers = {rec.dispatcher for rec in result.lineage}
    assert "CeleryDispatcher" in dispatchers
