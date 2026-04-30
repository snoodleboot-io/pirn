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


async def test_extensible_run_accepts_knot_whose_parent_finished():
    """A new knot whose parent has already completed is accepted and runs
    immediately in the next wave, using the cached result.

    This is the sequential chain pattern used by ``LoopSubTapestry``:
    each iteration registers the next *after* the current one finishes,
    so the new knot's parent is always in the completed results dict.
    The engine resolves the input from the cached result rather than
    re-running the parent.
    """
    parent_done = asyncio.Event()
    can_finish_other = asyncio.Event()

    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="px"))

    @knot
    async def _quick(x: int) -> int:
        parent_done.set()
        return x * 2

    @knot
    async def _slow_other(x: int) -> int:
        await can_finish_other.wait()
        return x

    with t:
        quick = _quick(x=p, _config=KnotConfig(id="quick"))
        other = _slow_other(x=p, _config=KnotConfig(id="other"))

    async def add_late_dependent():
        await parent_done.wait()
        # Yield so the engine records `quick`'s result before we register.
        await asyncio.sleep(0.01)
        with t:
            _add_ten(x=quick, _config=KnotConfig(id="late_dependent"))
        can_finish_other.set()

    adder = asyncio.create_task(add_late_dependent())

    result = await t.run(
        RunRequest(parameters={"x": 1}),
        terminals=[quick, other],
        extensible=True,
    )
    await adder
    # quick = 1*2 = 2; late_dependent = 2+10 = 12
    assert result.outputs["late_dependent"] == 12


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
