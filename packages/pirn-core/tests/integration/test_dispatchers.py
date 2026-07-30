"""Dispatcher tests, including ThreadDispatcher."""

from __future__ import annotations

import threading

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher
from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher
from pirn.tapestry import Tapestry


@knot
def sync_double(x: int) -> int:
    """A sync knot; will run in the dispatcher's thread when used with
    ThreadDispatcher."""
    return x * 2


@knot
async def async_double(x: int) -> int:
    return x * 2


def test_local_dispatcher_name():
    assert LocalDispatcher().name == "LocalDispatcher"


def test_thread_dispatcher_name():
    d = ThreadDispatcher(max_workers=2)
    try:
        assert d.name == "ThreadDispatcher"
    finally:
        d.shutdown()


async def test_local_dispatcher_runs_pipeline():
    with Tapestry(dispatcher=LocalDispatcher()) as t:
        p = Parameter("x", int, default=5)
        async_double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest())
    assert result.dispatcher == "LocalDispatcher"
    assert result.outputs["d"] == 10


async def test_thread_dispatcher_runs_pipeline():
    dispatcher = ThreadDispatcher(max_workers=4)
    try:
        with Tapestry(dispatcher=dispatcher) as t:
            p = Parameter("x", int, default=5)
            sync_double(x=p, _config=KnotConfig(id="d"))

        result = await t.run(RunRequest())
        assert result.dispatcher == "ThreadDispatcher"
        assert result.outputs["d"] == 10
    finally:
        dispatcher.shutdown()


async def test_thread_dispatcher_actually_uses_a_thread():
    """Verify a sync knot actually runs in a different thread than main."""
    main_thread = threading.get_ident()
    captured: dict[str, int] = {}

    @knot
    def capture(x: int) -> int:
        captured["tid"] = threading.get_ident()
        return x

    dispatcher = ThreadDispatcher(max_workers=2)
    try:
        with Tapestry(dispatcher=dispatcher) as t:
            p = Parameter("x", int, default=1)
            capture(x=p, _config=KnotConfig(id="c"))
        await t.run(RunRequest())
    finally:
        dispatcher.shutdown()

    assert "tid" in captured
    assert captured["tid"] != main_thread


@knot
async def probe_run_context() -> str:
    """Report whether the engine's ambient contextvars survived the hop."""
    from pirn.tapestry import _current_history, _current_run_id

    history_seen = _current_history.get(None) is not None
    run_id_seen = bool(_current_run_id.get(None))
    return f"history={history_seen} run_id={run_id_seen}"


async def test_thread_dispatcher_propagates_run_contextvars():
    """A knot on a worker thread must still see the run it belongs to.

    `run_in_executor` does not carry the ambient context. Before PIR-767 a knot
    dispatched to a thread saw `_current_history` and `_current_run_id` unset,
    so any inner run it started was written to no store and orphaned from its
    parent. Fixed by running the callable inside `contextvars.copy_context()`.
    """
    dispatcher = ThreadDispatcher(max_workers=2)
    try:
        with Tapestry(dispatcher=dispatcher) as t:
            probe_run_context(_config=KnotConfig(id="probe"))
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["probe"] == "history=True run_id=True"
    finally:
        dispatcher.shutdown()


def test_thread_dispatcher_keeps_its_own_executor():
    """The fix must not quietly swap the dedicated pool for the default one.

    `asyncio.to_thread` would copy the context too, but always uses the default
    executor — which would make `max_workers` and `shutdown()` no-ops.
    """
    dispatcher = ThreadDispatcher(max_workers=3)
    try:
        assert dispatcher._executor._max_workers == 3
    finally:
        dispatcher.shutdown()
