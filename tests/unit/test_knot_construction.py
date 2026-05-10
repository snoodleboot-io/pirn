"""Constructor convention tests.

The big Phase 2 redesign: knot kwargs that are Knots become parents,
others become config; _config=KnotConfig(id=...) is required;
construction-time validation.
"""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.optional import Optional
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry

# ---------------------------------------------------------------- subclass


class Add(Knot):
    async def process(self, a: int, b: int, **_: Any) -> int:
        return a + b


class StringFilter(Knot):
    """One parent, one config — exercises the partition rule."""

    async def process(self, items: list[str], pattern: str, **_: Any) -> list[str]:
        return [s for s in items if pattern in s]


# --------------------------------------------------------- required _config



class _StandaloneTests(unittest.TestCase):
    def test_construction_requires_config(self):
        with self.assertRaisesRegex(TypeError, "_config"):
            Add(
                a=Parameter("x", int, _config=KnotConfig(id="x")),
                b=Parameter("y", int, _config=KnotConfig(id="y")),
            )
    
    
    def test_construction_requires_knotconfig_instance(self):
        with self.assertRaisesRegex(TypeError, "KnotConfig"):
            Add(
                _config="not a KnotConfig",
                a=Parameter("x", int, _config=KnotConfig(id="x")),
                b=Parameter("y", int, _config=KnotConfig(id="y")),
            )
    
    
    def test_id_is_required(self):
        from pydantic import ValidationError
    
        with self.assertRaises(ValidationError):
            KnotConfig()  # no id
    
    
    def test_id_must_be_nonempty(self):
        from pydantic import ValidationError
    
        with self.assertRaises(ValidationError):
            KnotConfig(id="")
    
    
# ------------------------------------------------------- parent/config split


    def test_knot_value_becomes_parent(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        q = Parameter("y", int, _config=KnotConfig(id="y"))
        a = Add(a=p, b=q, _config=KnotConfig(id="add"))
        assert "a" in a.parents
        assert "b" in a.parents
        assert a.parents["a"] is p
        assert a.parents["b"] is q
        assert a.config_values == {}
    
    
    def test_non_knot_value_becomes_config(self):
        p = Parameter("items", list[str], _config=KnotConfig(id="items"))
        f = StringFilter(items=p, pattern="abc", _config=KnotConfig(id="filter"))
        assert "items" in f.parents
        assert "pattern" in f.config_values
        assert f.config_values["pattern"] == "abc"
    
    
    def test_mixed_parents_and_config(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        a = Add(a=p, b=p, _config=KnotConfig(id="self_add"))
        assert len(a.parents) == 2  # both kwargs are knots
        assert all(parent is p for parent in a.parents.values())
    
    
# ------------------------------------------------------- validation at ctor


    def test_missing_required_input_fails_at_construction(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        with self.assertRaisesRegex(TypeError, "missing required"):
            Add(a=p, _config=KnotConfig(id="add"))  # b is missing
    
    
    def test_unknown_knot_kwarg_accepted_as_implicit_dep(self):
        """A Knot-valued kwarg not in process signature is an implicit parent."""
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        q = Parameter("y", int, _config=KnotConfig(id="y"))
        node = Add(a=p, b=q, c=p, _config=KnotConfig(id="add"))
        assert "c" in node.parents
    
    
    def test_unknown_non_knot_kwarg_fails_at_construction(self):
        """A non-Knot unknown kwarg is always an error, even with **_."""
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        q = Parameter("y", int, _config=KnotConfig(id="y"))
        with self.assertRaisesRegex(TypeError, "unknown non-Knot kwarg"):
            Add(a=p, b=q, c=42, _config=KnotConfig(id="add"))
    
    
    def test_config_validation_at_construction(self):
        """A non-Knot kwarg whose value fails type validation should fail
        at construction, not at run time."""
        p = Parameter("items", list[str], _config=KnotConfig(id="items"))
        # pattern expected str; passing int should fail at construction
        with self.assertRaisesRegex(TypeError, "failed validation"):
            StringFilter(
                items=p,
                pattern=123,  # type: ignore[arg-type]
                _config=KnotConfig(id="bad"),
            )
    
    
# ------------------------------------------------------- decorator form


@knot
async def double(x: int) -> int:
    return x * 2


    def test_decorator_factory_constructs_knot(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        d = double(x=p, _config=KnotConfig(id="d"))
        assert isinstance(d, Knot)
        assert d.knot_id == "d"
        assert d.parents["x"] is p
    
    
    def test_decorator_factory_exposes_fn_and_class(self):
        assert callable(double.fn)
        assert isinstance(double.knot_class, type)
    
    
# ------------------------------------------------------- Optional wrapper


    def test_optional_wrapper_is_optional(self):
        from pirn.core.knot_factory import knot as knot_decorator

        @knot_decorator
        async def inner(x: int) -> int:
            return x

        p = Parameter("x", int, _config=KnotConfig(id="x"))
        i = inner(x=p, _config=KnotConfig(id="inner"))
        o = Optional(knot=i, _config=KnotConfig(id="opt"))
        assert isinstance(o, Optional)

    def test_regular_knot_is_not_optional(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        q = Parameter("y", int, _config=KnotConfig(id="y"))
        a = Add(a=p, b=q, _config=KnotConfig(id="a"))
        assert not isinstance(a, Optional)
    
    
# ------------------------------------------------------- immutability


    def test_immutability_after_construction(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        q = Parameter("y", int, _config=KnotConfig(id="y"))
        a = Add(a=p, b=q, _config=KnotConfig(id="a"))
        with self.assertRaisesRegex(AttributeError, "immutable"):
            a.some_new_attr = 123  # type: ignore[attr-defined]
    
    
# ------------------------------------------------------- tapestry registration


    def test_with_block_registers_knots(self):
        with Tapestry() as t:
            p = Parameter("x", int, _config=KnotConfig(id="x"))
            q = Parameter("y", int, _config=KnotConfig(id="y"))
            Add(a=p, b=q, _config=KnotConfig(id="a"))
        ids = sorted(k.knot_id for k in t.all_knots())
        assert ids == ["a", "x", "y"]
    
    
    def test_explicit_tapestry_kwarg_registers(self):
        t = Tapestry()
        Parameter("x", int, _config=KnotConfig(id="x"), tapestry=t)
        assert t.get("x") is not None
    
    
    def test_outside_with_block_no_registration(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        # No tapestry — knot is constructed but not registered anywhere.
        # We just check that it's a valid Knot.
        assert p.knot_id == "x"
    
    
# ------------------------------------------------------- duplicate id


    def test_duplicate_id_in_tapestry_raises(self):
        t = Tapestry()
        Parameter("x", int, _config=KnotConfig(id="dup"), tapestry=t)
        with self.assertRaisesRegex(ValueError, "already registered"):
            Parameter("y", int, _config=KnotConfig(id="dup"), tapestry=t)
    
    
# ------------------------------------------------------- error_policy


    def test_default_error_policy(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        q = Parameter("y", int, _config=KnotConfig(id="y"))
        a = Add(a=p, b=q, _config=KnotConfig(id="a"))
        assert a.config.error_policy is ErrorPolicy.SKIP_IF_PARENT_FAILED
    
    
    def test_explicit_error_policy(self):
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        q = Parameter("y", int, _config=KnotConfig(id="y"))
        a = Add(
            a=p,
            b=q,
            _config=KnotConfig(id="a", error_policy=ErrorPolicy.RECEIVE_ERRORS),
        )
        assert a.config.error_policy is ErrorPolicy.RECEIVE_ERRORS
