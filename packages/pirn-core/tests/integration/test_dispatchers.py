"""Dispatcher tests, including ThreadDispatcher."""

from __future__ import annotations

import threading

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.parameter import Parameter
from pirn.core.run_context_vars import RunContextVars
from pirn.core.run_request import RunRequest
from pirn.engine.dispatchers.local_dispatcher import LocalDispatcher
from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher
from pirn.tapestry import Tapestry


@KnotFactory.knot
def sync_double(x: int) -> int:
    """A sync knot; will run in the dispatcher's thread when used with
    ThreadDispatcher."""
    return x * 2


@KnotFactory.knot
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

    @KnotFactory.knot
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


@KnotFactory.knot
async def probe_run_context() -> str:
    """Report whether the engine's ambient contextvars survived the hop."""

    history_seen = RunContextVars.history.get(None) is not None
    run_id_seen = bool(RunContextVars.run_id.get(None))
    return f"history={history_seen} run_id={run_id_seen}"


async def test_thread_dispatcher_propagates_run_contextvars():
    """A knot on a worker thread must still see the run it belongs to.

    `run_in_executor` does not carry the ambient context. Before PIR-767 a knot
    dispatched to a thread saw `RunContextVars.history` and `RunContextVars.run_id` unset,
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


def test_local_dispatcher_runs_containers_on_itself():
    """The default ``dispatcher_for_container`` is the identity (PIR-870)."""
    dispatcher = LocalDispatcher()
    assert dispatcher.dispatcher_for_container(object()) is dispatcher  # type: ignore[arg-type]


def test_thread_dispatcher_routes_containers_to_a_local_dispatcher():
    """A container must not spend a pool worker awaiting its own inner run (PIR-870)."""
    dispatcher = ThreadDispatcher(max_workers=2)
    try:
        container_dispatcher = dispatcher.dispatcher_for_container(object())  # type: ignore[arg-type]
        assert isinstance(container_dispatcher, LocalDispatcher)
        # Stable across calls: it is one shared instance, not built fresh
        # each time.
        assert dispatcher.dispatcher_for_container(object()) is container_dispatcher  # type: ignore[arg-type]
    finally:
        dispatcher.shutdown()
