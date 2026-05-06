"""Tapestry tests."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.tapestry import _current_tapestry, Tapestry, current_tapestry


@knot
async def _f(x: int) -> int:
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
