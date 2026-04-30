"""Tests for mid-run extension (Tier 4).

The engine's ``extensible_store`` mode subscribes to a tapestry store
for new-knot events and merges them into the shed between waves.
``Tapestry.run(extensible=True)`` opts in.
"""

from __future__ import annotations

import asyncio

import pytest

from pirn.backends.in_memory.in_memory_store import InMemoryStore
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.engine.shed.shed_error import ShedError
from pirn.tapestry import Tapestry

# ---------------------------------------------------- store subscribe API


def test_in_memory_store_subscribe_receives_new_knots():
    store = InMemoryStore()
    received: list = []
    token = store.subscribe(received.append)

    p = Parameter("x", int, _config=KnotConfig(id="px"))
    store.register(p)

    assert received == [p]
    store.unsubscribe(token)


def test_in_memory_store_unsubscribe_stops_callback():
    store = InMemoryStore()
    received: list = []
    token = store.subscribe(received.append)
    store.unsubscribe(token)

    p = Parameter("x", int, _config=KnotConfig(id="px"))
    store.register(p)
    assert received == []


def test_in_memory_store_idempotent_register_does_not_re_notify():
    """Re-registering the same knot instance is a no-op; subscribers
    should not see duplicate notifications."""
    store = InMemoryStore()
    received: list = []
    store.subscribe(received.append)

    p = Parameter("x", int, _config=KnotConfig(id="px"))
    store.register(p)
    store.register(p)  # idempotent
    assert len(received) == 1


def test_in_memory_store_subscriber_exception_does_not_break_register():
    store = InMemoryStore()

    def bad(_):
        raise RuntimeError("subscriber broken")

    store.subscribe(bad)

    # Should not raise.
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    store.register(p)
    assert store.get("px") is p


# ---------------------------------------------------- mid-run extension


@knot
async def _double(x: int) -> int:
    return x * 2


@knot
async def _add_ten(x: int) -> int:
    return x + 10


async def test_extensible_run_picks_up_knot_added_during_run():
    """A knot registered during the run that depends on a knot that
    hasn't run yet must be picked up."""
    with Tapestry() as t:
        # Build the initial pipeline: just a parameter.
        p = Parameter("x", int, _config=KnotConfig(id="px"))

    # Register a child mid-run by using a custom inner knot whose
    # process registers a downstream knot.
    @knot
    async def _registrar(x: int) -> int:
        # Register a new dependent knot mid-run.  The child consumes
        # this very knot's output.
        Parameter("downstream_input", int, default=99, tapestry=t, _config=KnotConfig(id="late"))
        return x

    with t:
        registrar = _registrar(x=p, _config=KnotConfig(id="r"))

    # Without extensible mode, the late knot won't be picked up.
    result = await t.run(
        RunRequest(parameters={"x": 1}),
        terminals=[registrar],
    )
    assert "late" not in result.outputs

    # Reset the tapestry and try again with extensible=True.
    with Tapestry() as t2:
        p2 = Parameter("x", int, _config=KnotConfig(id="px"))

    @knot
    async def _registrar2(x: int) -> int:
        Parameter(
            "downstream_input",
            int,
            default=99,
            tapestry=t2,
            _config=KnotConfig(id="late"),
        )
        return x

    with t2:
        registrar2 = _registrar2(x=p2, _config=KnotConfig(id="r"))

    result2 = await t2.run(
        RunRequest(parameters={"x": 1}),
        terminals=None,  # let it pick up newly-added terminal too
        extensible=True,
    )
    # The late-arriving Parameter has default=99, so it executes and
    # produces an output keyed by id "late".
    assert "late" in result2.outputs
    assert result2.outputs["late"] == 99


async def test_extensible_run_rejects_knot_whose_parent_finished():
    """If a new knot depends on a knot that already produced a result,
    the merge raises ``ShedError``.

    This is the strict design: the engine refuses to schedule a
    newcomer whose parent has already completed because doing so
    silently would either re-run the parent (wasteful, breaks lineage)
    or use the cached result without the user being aware that they
    constructed a race condition.  The error directs the user to
    register dependents *before* their parents run — typically by
    constructing the dependent inside the same wave.
    """
    parent_done = asyncio.Event()
    can_finish_other = asyncio.Event()

    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="px"))

    @knot
    async def _quick(x: int) -> int:
        # Finish quickly; we'll register a knot depending on this
        # before the run as a whole completes.
        parent_done.set()
        return x * 2

    @knot
    async def _slow_other(x: int) -> int:
        # This knot keeps the run alive long enough for the late
        # registration to land.
        await can_finish_other.wait()
        return x

    with t:
        quick = _quick(x=p, _config=KnotConfig(id="quick"))
        other = _slow_other(x=p, _config=KnotConfig(id="other"))

    async def add_late_dependent():
        await parent_done.wait()
        # Yield so the engine has a chance to record `quick`'s result
        # in the results dict before we register the dependent.
        await asyncio.sleep(0.01)
        with t:
            _add_ten(x=quick, _config=KnotConfig(id="late_dependent"))
        # Now allow the run to finish.
        can_finish_other.set()

    adder = asyncio.create_task(add_late_dependent())

    with pytest.raises(ShedError, match="already completed"):
        await t.run(
            RunRequest(parameters={"x": 1}),
            terminals=[quick, other],
            extensible=True,
        )
    await adder


async def test_extensible_run_with_non_subscribable_store_raises():
    """``extensible=True`` against a TapestryStore that doesn't
    implement the SubscribableStore protocol must error clearly."""

    class NotSubscribable:
        def register(self, knot):
            pass

        def get(self, knot_id):
            return None

        def all(self):
            return []

        def snapshot(self):
            from pirn.backends.base.tapestry_snapshot import TapestrySnapshot

            return TapestrySnapshot(knot_ids=[])

    t = Tapestry(store=NotSubscribable())
    p = Parameter("x", int, default=1, tapestry=t, _config=KnotConfig(id="px"))

    with pytest.raises(TypeError, match="subscribe"):
        await t.run(
            RunRequest(),
            terminals=[p],
            extensible=True,
        )


async def test_non_extensible_run_ignores_late_knots():
    """``extensible=False`` (the default) means knots registered
    mid-run are simply ignored for this run."""
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="px"))

    @knot
    async def _registrar(x: int) -> int:
        Parameter("late", int, default=99, tapestry=t, _config=KnotConfig(id="late"))
        return x * 2

    with t:
        registrar = _registrar(x=p, _config=KnotConfig(id="r"))

    result = await t.run(
        RunRequest(parameters={"x": 1}),
        terminals=[registrar],
    )
    assert "late" not in result.outputs
    assert result.outputs["r"] == 2  # registrar succeeded
    # The late knot is in the tapestry but wasn't part of this run.
    assert t.get("late") is not None
