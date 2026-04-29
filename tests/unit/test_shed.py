"""Shed (per-run cross-section) tests.

The shed is a derived, read-only view of which knots will run for a
given terminal-set, with parents walked and execution order computed.
It is an engine internal — imported from ``pirn.engine.shed``, not from
the public package surface.
"""

from __future__ import annotations

import pytest

from pirn import KnotConfig, Parameter, knot
from pirn.engine.shed import Shed, ShedError


@knot
async def f(x: int) -> int:
    return x


def test_single_knot():
    p = Parameter("x", int, _config=KnotConfig(id="p"))
    s = Shed.from_terminals(p)
    assert len(s) == 1
    assert "p" in s


def test_chain_walks_parents():
    p = Parameter("x", int, _config=KnotConfig(id="p"))
    a = f(x=p, _config=KnotConfig(id="a"))
    b = f(x=a, _config=KnotConfig(id="b"))
    s = Shed.from_terminals(b)
    assert len(s) == 3
    order = s.topological_order()
    assert order.index("p") < order.index("a") < order.index("b")


def test_diamond():
    p = Parameter("x", int, _config=KnotConfig(id="p"))
    a = f(x=p, _config=KnotConfig(id="a"))
    b = f(x=p, _config=KnotConfig(id="b"))

    @knot
    async def join(left: int, right: int) -> int:
        return left + right

    j = join(left=a, right=b, _config=KnotConfig(id="j"))
    s = Shed.from_terminals(j)
    assert len(s) == 4
    order = s.topological_order()
    assert order.index("p") < order.index("a") < order.index("j")
    assert order.index("p") < order.index("b") < order.index("j")


def test_multiple_terminals_union():
    p = Parameter("x", int, _config=KnotConfig(id="p"))
    a = f(x=p, _config=KnotConfig(id="a"))
    b = f(x=p, _config=KnotConfig(id="b"))
    s = Shed.from_terminals([a, b])
    assert len(s) == 3
    assert {"p", "a", "b"} == set(s.knots)


def test_roots_and_leaves():
    p = Parameter("x", int, _config=KnotConfig(id="p"))
    a = f(x=p, _config=KnotConfig(id="a"))
    b = f(x=a, _config=KnotConfig(id="b"))
    s = Shed.from_terminals(b)
    assert [k.knot_id for k in s.roots()] == ["p"]
    assert [k.knot_id for k in s.leaves()] == ["b"]


def test_unknown_lookup_raises():
    p = Parameter("x", int, _config=KnotConfig(id="p"))
    s = Shed.from_terminals(p)
    with pytest.raises(ShedError):
        s.knot("nope")


def test_two_distinct_knots_with_same_id_raises():
    """The shed builder catches id collision while walking."""
    p1 = Parameter("x", int, _config=KnotConfig(id="dup"))
    p2 = Parameter("y", int, _config=KnotConfig(id="dup"))
    # f1 has p1 as parent; f2 has p2 as parent.
    f1 = f(x=p1, _config=KnotConfig(id="a"))
    f2 = f(x=p2, _config=KnotConfig(id="b"))
    with pytest.raises(ShedError, match="share id"):
        Shed.from_terminals([f1, f2])
