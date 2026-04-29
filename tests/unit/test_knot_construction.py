"""Constructor convention tests.

The big Phase 2 redesign: knot kwargs that are Knots become parents,
others become config; _config=KnotConfig(id=...) is required;
construction-time validation.
"""

from __future__ import annotations

import pytest

from pirn import (
    ErrorPolicy,
    Knot,
    KnotConfig,
    Optional,
    Parameter,
    Tapestry,
    knot,
)

# ---------------------------------------------------------------- subclass


class Add(Knot):
    async def process(self, a: int, b: int) -> int:
        return a + b


class StringFilter(Knot):
    """One parent, one config — exercises the partition rule."""

    async def process(self, items: list[str], pattern: str) -> list[str]:
        return [s for s in items if pattern in s]


# --------------------------------------------------------- required _config


def test_construction_requires_config():
    with pytest.raises(TypeError, match="_config"):
        Add(
            a=Parameter("x", int, _config=KnotConfig(id="x")),
            b=Parameter("y", int, _config=KnotConfig(id="y")),
        )


def test_construction_requires_knotconfig_instance():
    with pytest.raises(TypeError, match="KnotConfig"):
        Add(
            _config="not a KnotConfig",
            a=Parameter("x", int, _config=KnotConfig(id="x")),
            b=Parameter("y", int, _config=KnotConfig(id="y")),
        )


def test_id_is_required():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        KnotConfig()  # no id


def test_id_must_be_nonempty():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        KnotConfig(id="")


# ------------------------------------------------------- parent/config split


def test_knot_value_becomes_parent():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    q = Parameter("y", int, _config=KnotConfig(id="y"))
    a = Add(a=p, b=q, _config=KnotConfig(id="add"))
    assert "a" in a.parents
    assert "b" in a.parents
    assert a.parents["a"] is p
    assert a.parents["b"] is q
    assert a.config_values == {}


def test_non_knot_value_becomes_config():
    p = Parameter("items", list[str], _config=KnotConfig(id="items"))
    f = StringFilter(items=p, pattern="abc", _config=KnotConfig(id="filter"))
    assert "items" in f.parents
    assert "pattern" in f.config_values
    assert f.config_values["pattern"] == "abc"


def test_mixed_parents_and_config():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    a = Add(a=p, b=p, _config=KnotConfig(id="self_add"))
    assert len(a.parents) == 2  # both kwargs are knots
    assert all(parent is p for parent in a.parents.values())


# ------------------------------------------------------- validation at ctor


def test_missing_required_input_fails_at_construction():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    with pytest.raises(TypeError, match="missing required"):
        Add(a=p, _config=KnotConfig(id="add"))  # b is missing


def test_unknown_kwarg_fails_at_construction():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    q = Parameter("y", int, _config=KnotConfig(id="y"))
    with pytest.raises(TypeError, match="unknown kwarg"):
        Add(a=p, b=q, c=p, _config=KnotConfig(id="add"))


def test_config_validation_at_construction():
    """A non-Knot kwarg whose value fails type validation should fail
    at construction, not at run time."""
    p = Parameter("items", list[str], _config=KnotConfig(id="items"))
    # pattern expected str; passing int should fail at construction
    with pytest.raises(TypeError, match="failed validation"):
        StringFilter(
            items=p,
            pattern=123,  # type: ignore[arg-type]
            _config=KnotConfig(id="bad"),
        )


# ------------------------------------------------------- decorator form


@knot
async def double(x: int) -> int:
    return x * 2


def test_decorator_factory_constructs_knot():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    d = double(x=p, _config=KnotConfig(id="d"))
    assert isinstance(d, Knot)
    assert d.knot_id == "d"
    assert d.parents["x"] is p


def test_decorator_factory_exposes_fn_and_class():
    assert callable(double.fn)
    assert isinstance(double.knot_class, type)


# ------------------------------------------------------- Optional mixin


def test_optional_mixin_marks_class():
    class Opt(Optional, Knot):
        async def process(self, x: int) -> int:
            return x

    p = Parameter("x", int, _config=KnotConfig(id="x"))
    o = Opt(x=p, _config=KnotConfig(id="opt"))
    assert o.is_optional is True


def test_regular_knot_is_not_optional():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    q = Parameter("y", int, _config=KnotConfig(id="y"))
    a = Add(a=p, b=q, _config=KnotConfig(id="a"))
    assert a.is_optional is False


# ------------------------------------------------------- immutability


def test_immutability_after_construction():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    q = Parameter("y", int, _config=KnotConfig(id="y"))
    a = Add(a=p, b=q, _config=KnotConfig(id="a"))
    with pytest.raises(AttributeError, match="immutable"):
        a.some_new_attr = 123  # type: ignore[attr-defined]


# ------------------------------------------------------- tapestry registration


def test_with_block_registers_knots():
    with Tapestry() as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        q = Parameter("y", int, _config=KnotConfig(id="y"))
        Add(a=p, b=q, _config=KnotConfig(id="a"))
    ids = sorted(k.knot_id for k in t.all_knots())
    assert ids == ["a", "x", "y"]


def test_explicit_tapestry_kwarg_registers():
    t = Tapestry()
    Parameter("x", int, _config=KnotConfig(id="x"), tapestry=t)
    assert t.get("x") is not None


def test_outside_with_block_no_registration():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    # No tapestry — knot is constructed but not registered anywhere.
    # We just check that it's a valid Knot.
    assert p.knot_id == "x"


# ------------------------------------------------------- duplicate id


def test_duplicate_id_in_tapestry_raises():
    t = Tapestry()
    Parameter("x", int, _config=KnotConfig(id="dup"), tapestry=t)
    with pytest.raises(ValueError, match="already registered"):
        Parameter("y", int, _config=KnotConfig(id="dup"), tapestry=t)


# ------------------------------------------------------- error_policy


def test_default_error_policy():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    q = Parameter("y", int, _config=KnotConfig(id="y"))
    a = Add(a=p, b=q, _config=KnotConfig(id="a"))
    assert a.config.error_policy is ErrorPolicy.SKIP_IF_PARENT_FAILED


def test_explicit_error_policy():
    p = Parameter("x", int, _config=KnotConfig(id="x"))
    q = Parameter("y", int, _config=KnotConfig(id="y"))
    a = Add(
        a=p,
        b=q,
        _config=KnotConfig(id="a", error_policy=ErrorPolicy.RECEIVE_ERRORS),
    )
    assert a.config.error_policy is ErrorPolicy.RECEIVE_ERRORS
