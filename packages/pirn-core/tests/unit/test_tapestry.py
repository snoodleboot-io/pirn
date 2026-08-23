"""Tapestry tests."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_result import RunResult
from pirn.emitters.base import Emitter
from pirn.tapestry import Tapestry, _current_tapestry, current_tapestry


@knot
async def _f(x: int) -> int:
    return x


class _RecordingEmitter(Emitter):
    """Captures the run results it is handed."""

    def __init__(self) -> None:
        self.run_results: list[RunResult] = []

    async def on_run_result(self, result: RunResult) -> None:
        self.run_results.append(result)


# (tapestry, emitter) queued for a knot to register while a run is in flight.
_pending_emitter: list[tuple[Tapestry, Emitter]] = []


@knot
async def _adds_emitter(x: int) -> int:
    """Subscribe an emitter from inside the run that must not see it."""
    for tapestry, emitter in _pending_emitter:
        tapestry.add_emitter(emitter)
    return x


class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    def test_empty_tapestry(self):
        t = Tapestry()
        assert t.all_knots() == []
        assert t.terminals() == []

    def test_with_block_sets_contextvar(self):
        assert _current_tapestry.get(None) is None
        with Tapestry() as t:
            assert _current_tapestry.get(None) is t
            assert current_tapestry() is t
        assert _current_tapestry.get(None) is None

    def test_with_block_restores_outer_context(self):
        """Nested with-blocks restore the outer tapestry on exit."""
        with Tapestry() as outer:
            assert current_tapestry() is outer
            with Tapestry() as inner:
                assert current_tapestry() is inner
            assert current_tapestry() is outer

    def test_registration_via_with(self):
        with Tapestry() as t:
            p = Parameter("x", int)
            d = _f(x=p, _config=KnotConfig(id="d"))
        assert t.get("param:x") is p
        assert t.get("d") is d

    def test_registration_via_explicit_kwarg(self):
        t = Tapestry()
        Parameter("x", int, tapestry=t)
        assert t.get("param:x") is not None

    def test_terminals_simple_chain(self):
        with Tapestry() as t:
            p = Parameter("x", int)
            d = _f(x=p, _config=KnotConfig(id="d"))
        terminals = t.terminals()
        assert len(terminals) == 1
        assert terminals[0] is d

    def test_terminals_multiple(self):
        with Tapestry() as t:
            p = Parameter("x", int)
            a = _f(x=p, _config=KnotConfig(id="a"))
            b = _f(x=p, _config=KnotConfig(id="b"))
        terminals = sorted(t.terminals(), key=lambda k: k.knot_id)
        assert [k.knot_id for k in terminals] == ["a", "b"]

    def test_register_same_instance_twice_is_idempotent(self):
        t = Tapestry()
        p = Parameter("x", int, tapestry=t)
        # The Parameter constructor already registered it; do it again.
        t.register(p)
        assert len([k for k in t.all_knots() if k is p]) == 1

    def test_register_different_instance_same_id_raises(self):
        t = Tapestry()
        p1 = Parameter("x", int, _config=KnotConfig(id="dup"), tapestry=t)
        with self.assertRaisesRegex(ValueError, "already registered"):
            Parameter("y", int, _config=KnotConfig(id="dup"), tapestry=t)
        # Original still there.
        assert t.get("dup") is p1

    async def test_run_with_no_terminals_raises(self):
        t = Tapestry()
        with self.assertRaisesRegex(ValueError, "no knots"):
            await t.run()

    async def test_run_explicit_terminals(self):
        """Specify terminals manually rather than via inferred leaves."""
        from pirn.core.run_request import RunRequest

        with Tapestry() as t:
            p = Parameter("x", int)
            a = _f(x=p, _config=KnotConfig(id="a"))
            # Add another knot that won't be requested.
            _f(x=p, _config=KnotConfig(id="b"))

        result = await t.run(RunRequest(parameters={"x": 5}), terminals=a)
        assert result.succeeded
        assert "a" in result.outputs
        # b is not part of this run because it wasn't reachable from the
        # requested terminal.
        assert "b" not in result.outputs

    # --------------------------------------------------------- emitter tests

    def test_add_and_remove_emitter_by_identity(self):
        from pirn.emitters.log import LogEmitter

        t = Tapestry()
        e1 = LogEmitter()
        e2 = LogEmitter()
        t.add_emitter(e1)
        t.add_emitter(e2)
        assert len(t.emitters) == 2

        t.remove_emitter(e1)
        assert len(t.emitters) == 1
        assert t.emitters[0] is e2

    def test_remove_emitter_raises_when_not_registered(self):
        from pirn.emitters.log import LogEmitter

        t = Tapestry()
        e = LogEmitter()
        with self.assertRaisesRegex(ValueError, "not registered"):
            t.remove_emitter(e)

    def test_remove_emitter_uses_identity_not_equality(self):
        """Two equal-looking emitters must be distinguished by identity."""
        from pirn.emitters.log import LogEmitter

        t = Tapestry()
        e1 = LogEmitter()
        e2 = LogEmitter()
        t.add_emitter(e1)

        # e2 is not e1 even if they're the same type.
        with self.assertRaisesRegex(ValueError, "not registered"):
            t.remove_emitter(e2)

    def test_emitters_property_returns_copy(self):
        from pirn.emitters.log import LogEmitter

        t = Tapestry()
        e = LogEmitter()
        t.add_emitter(e)
        snapshot = t.emitters
        snapshot.clear()
        assert len(t.emitters) == 1

    async def test_run_snapshots_the_emitter_list_at_entry(self):
        """A subscription change mid-run must not alter the run already in flight.

        ``run()`` used to hand the live ``_emitters`` list straight to the
        engine, so an ``add_emitter`` from another task landed in the running
        run's emitter set -- a run fanning events to an observer its caller
        never registered for it (PIR-809).  The engine re-reads the list at
        run end to deliver ``on_run_result``, which is where the late arrival
        showed up.

        An emitter is registered up front because the engine replaces an empty
        list with a fresh one (``emitters or []``), which would hide the alias.
        """
        from pirn.core.run_request import RunRequest

        early = _RecordingEmitter()
        late = _RecordingEmitter()

        with Tapestry() as t:
            p = Parameter("x", int, default=1)
            a = _adds_emitter(x=p, _config=KnotConfig(id="a"))
        t.add_emitter(early)

        _pending_emitter.append((t, late))
        try:
            await t.run(RunRequest(), terminals=a)
        finally:
            _pending_emitter.clear()

        # The run's own emitter was served; the late arrival is registered for
        # subsequent runs but saw nothing from this one.
        assert len(early.run_results) == 1
        assert t.emitters[-1] is late
        assert late.run_results == []
