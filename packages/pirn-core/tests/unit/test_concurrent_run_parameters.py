"""Concurrent runs against one shared ``Tapestry`` must not cross-bind parameters.

Building the graph once at startup and serving many requests from it is the
obvious way to use a ``Tapestry`` as a long-lived service object.  Before
PIR-802 that produced silent wrong answers: run identity was carried in a
ContextVar (correctly task-local) while the parameter *value* was written onto
the shared ``Parameter`` knot instance, so four concurrent runs all computed
with whichever request bound last.  Every run still succeeded and recorded a
plausible-looking lineage entry, which is what made it dangerous.

These tests pin the contract that binding is per-run.
"""

from __future__ import annotations

import asyncio
import pickle
import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.exceptions.unbound_parameter_error import UnboundParameterError
from pirn.tapestry import Tapestry, current_run_id

# run_id -> the x value that knot actually computed with.
_seen: dict[str | None, int] = {}

# Values passed to Parameter.bind_value during a run; must stay empty.
_bind_value_calls: list[Any] = []


@knot
async def _record(x: int) -> int:
    """Record which x this run's execution actually received."""
    # Yield control so concurrent runs genuinely interleave rather than
    # each running to completion before the next starts.
    await asyncio.sleep(0.01)
    _seen[current_run_id()] = x
    return x


@knot
async def _double(x: int) -> int:
    await asyncio.sleep(0.01)
    return x * 2


class ConcurrentRunParameterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _seen.clear()

    async def test_concurrent_runs_each_observe_their_own_parameters(self):
        """The core defect: four concurrent runs, four distinct parameter values."""
        with Tapestry() as t:
            p = Parameter("x", int)
            a = _record(x=p, _config=KnotConfig(id="a"))

        submitted = (10, 11, 12, 13)
        requests = [RunRequest(parameters={"x": n}) for n in submitted]
        expected = {r.run_id: n for r, n in zip(requests, submitted, strict=True)}

        results = await asyncio.gather(*(t.run(r, terminals=a) for r in requests))

        assert all(r.succeeded for r in results)
        # Run identity was always correct; the point is that the *value* now
        # matches it too.
        assert _seen == expected

    async def test_concurrent_runs_return_their_own_outputs(self):
        """The value must also come back out through the run's outputs."""
        with Tapestry() as t:
            p = Parameter("x", int)
            a = _double(x=p, _config=KnotConfig(id="a"))

        submitted = (1, 2, 3, 4)
        requests = [RunRequest(parameters={"x": n}) for n in submitted]

        results = await asyncio.gather(*(t.run(r, terminals=a) for r in requests))

        assert [r.outputs["a"] for r in results] == [2, 4, 6, 8]

    async def test_a_run_does_not_mutate_the_shared_parameter(self):
        """The graph is shared; a run must leave it exactly as it found it.

        If a run writes its value onto the shared ``Parameter``, that value
        leaks into the *next* run that omits the binding — a stale-read defect
        even without concurrency.
        """
        with Tapestry() as t:
            p = Parameter("x", int, default=0)
            a = _double(x=p, _config=KnotConfig(id="a"))

        first = await t.run(RunRequest(parameters={"x": 7}), terminals=a)
        assert first.outputs["a"] == 14

        # No binding supplied: must fall back to the declared default, not to
        # whatever the previous run left behind.
        second = await t.run(RunRequest(), terminals=a)
        assert second.outputs["a"] == 0

    async def test_concurrent_runs_are_correct_under_the_thread_dispatcher(self):
        """The binding must survive the dispatcher's ``copy_context()`` thread hop."""
        from pirn.engine.dispatchers.thread_dispatcher import ThreadDispatcher

        with Tapestry() as t:
            p = Parameter("x", int)
            a = _double(x=p, _config=KnotConfig(id="a"))

        requests = [RunRequest(parameters={"x": n}) for n in (1, 2, 3, 4)]

        results = await asyncio.gather(
            *(t.run(r, terminals=a, dispatcher=ThreadDispatcher()) for r in requests)
        )

        assert [r.outputs["a"] for r in results] == [2, 4, 6, 8]

    async def test_concurrent_runs_mixing_bound_and_default_values(self):
        """A run that omits the binding gets the default even while others bind."""
        with Tapestry() as t:
            p = Parameter("x", int, default=99)
            a = _record(x=p, _config=KnotConfig(id="a"))

        bound = [RunRequest(parameters={"x": n}) for n in (1, 2)]
        defaulted = [RunRequest() for _ in range(2)]
        expected: dict[str | None, Any] = {bound[0].run_id: 1, bound[1].run_id: 2}
        for r in defaulted:
            expected[r.run_id] = 99

        await asyncio.gather(*(t.run(r, terminals=a) for r in bound + defaulted))

        assert _seen == expected


class _BindValueSpy(Parameter):
    """A ``Parameter`` that records every ``bind_value`` call made on it."""

    def bind_value(self, value: Any) -> None:
        _bind_value_calls.append(value)
        super().bind_value(value)


class EngineDoesNotUseBindValueTests(unittest.IsolatedAsyncioTestCase):
    """``bind_value`` writes to shared graph state; the engine must not call it.

    PIR-802 deliberately kept ``bind_value`` for direct, single-owner use of a
    standalone ``Parameter``, so it is not deprecated -- but it is now the one
    call that would reintroduce that defect.  A refactor that "simplified"
    ``bound_copy`` back into it would restore silent cross-run contamination
    and pass every other test in this file, because those assert on observable
    values and a single sequential run looks identical either way.  This one
    watches the call itself.
    """

    def setUp(self) -> None:
        _bind_value_calls.clear()

    def tearDown(self) -> None:
        _bind_value_calls.clear()

    async def test_a_run_never_calls_bind_value_on_the_shared_parameter(self):
        with Tapestry() as t:
            p = _BindValueSpy("x", int)
            a = _double(x=p, _config=KnotConfig(id="a"))

        result = await t.run(RunRequest(parameters={"x": 21}), terminals=a)

        assert result.outputs["a"] == 42
        assert _bind_value_calls == [], (
            f"engine called bind_value on the shared Parameter: {_bind_value_calls}"
        )

    async def test_a_defaulted_run_never_calls_bind_value_either(self):
        """The no-binding-supplied path must not write the default onto the graph."""
        with Tapestry() as t:
            p = _BindValueSpy("x", int, default=5)
            a = _double(x=p, _config=KnotConfig(id="a"))

        await t.run(RunRequest(), terminals=a)

        assert _bind_value_calls == []


class BoundCopyTests(unittest.TestCase):
    """Pin the properties of the run-scoped copy the engine binds onto.

    These exist so the fix is not later "simplified" into a ContextVar.  A
    ContextVar would be empty in a worker process, which would silently break
    the Ray/Dask/Celery dispatchers -- they pickle the knot and run it
    elsewhere, so the value has to travel *on the knot*.
    """

    def test_the_copy_keeps_the_knot_id(self):
        """Shed, results and lineage are all keyed by knot_id."""
        with Tapestry():
            p = Parameter("x", int)

        assert p.bound_copy(1).knot_id == p.knot_id

    def test_the_copy_does_not_touch_the_original(self):
        with Tapestry():
            p = Parameter("x", int)

        p.bound_copy(1)

        # The shared graph knot is still unbound, so it cannot leak a value
        # into any other run.
        with self.assertRaises(UnboundParameterError):
            asyncio.run(p.process())

    def test_the_copy_does_not_register_with_the_tapestry(self):
        """It belongs to one run, not to the graph."""
        with Tapestry() as t:
            p = Parameter("x", int)
        before = len(t._store.all())

        p.bound_copy(1)

        assert len(t._store.all()) == before

    def test_the_binding_survives_pickling(self):
        """Process-boundary dispatchers serialize the knot to a worker."""
        with Tapestry():
            p = Parameter("x", int)

        revived = pickle.loads(pickle.dumps(p.bound_copy(42)))

        assert asyncio.run(revived.process()) == 42
