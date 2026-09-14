from __future__ import annotations

import asyncio
import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry


class Add(Knot):
    async def process(self, a: int, b: int, **_: Any) -> int:
        return a + b


class NoOutput(Knot):
    async def process(self, x: int, **_: Any) -> None:
        pass


class TestKnotHelpers(unittest.TestCase):
    def test_is_knot_cls_true(self) -> None:
        self.assertTrue(Knot._is_knot_cls(Knot))
        self.assertTrue(Knot._is_knot_cls(Add))

    def test_is_knot_cls_false_for_non_class(self) -> None:
        self.assertFalse(Knot._is_knot_cls(42))
        self.assertFalse(Knot._is_knot_cls("string"))

    def test_is_knot_cls_false_for_non_knot(self) -> None:
        self.assertFalse(Knot._is_knot_cls(int))

    def test_extract_coercible_type_plain_type_returns_none(self) -> None:
        self.assertIsNone(Knot._extract_coercible_type(int))

    def test_extract_coercible_type_union_with_knot(self) -> None:
        from typing import Union

        # Deliberately the typing.Union form (not `Knot | int`): this exercises
        # _extract_coercible_type's `origin is Union` branch specifically, which
        # is distinct from its PEP-604 types.UnionType branch. Mirrors the
        # UP007 suppression the source itself carries where Union is required.
        result = Knot._extract_coercible_type(Union[Knot, int])  # noqa: UP007
        self.assertIsNotNone(result)
        coerce_type, _adapter_type = result
        self.assertIs(coerce_type, int)


class TestKnotConstruction(unittest.TestCase):
    def _p(self, name: str, type_=int) -> Parameter:
        return Parameter(name, type_, _config=KnotConfig(id=name))

    def test_requires_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "_config"):
            Add(a=self._p("a"), b=self._p("b"))

    def test_requires_knotconfig_instance(self) -> None:
        with self.assertRaisesRegex(TypeError, "KnotConfig"):
            Add(a=self._p("a"), b=self._p("b"), _config="not-a-config")

    def test_knot_valued_kwargs_become_parents(self) -> None:
        p = self._p("a")
        q = self._p("b")
        node = Add(a=p, b=q, _config=KnotConfig(id="add"))
        self.assertIn("a", node.parents)
        self.assertIn("b", node.parents)
        self.assertIs(node.parents["a"], p)

    def test_non_knot_values_become_config(self) -> None:
        class Filter(Knot):
            async def process(self, items: list[str], pattern: str, **_: Any) -> list[str]:
                return [s for s in items if pattern in s]

        items = Parameter("items", list[str], _config=KnotConfig(id="items"))
        f = Filter(items=items, pattern="abc", _config=KnotConfig(id="f"))
        self.assertIn("pattern", f.config_values)
        self.assertEqual(f.config_values["pattern"], "abc")

    def test_missing_required_input_fails(self) -> None:
        with self.assertRaisesRegex(TypeError, "missing required"):
            Add(a=self._p("a"), _config=KnotConfig(id="add"))

    def test_unknown_non_knot_kwarg_fails(self) -> None:
        with self.assertRaisesRegex(TypeError, "unknown non-Knot kwarg"):
            Add(a=self._p("a"), b=self._p("b"), c=42, _config=KnotConfig(id="add"))

    def test_unknown_knot_kwarg_accepted_as_implicit_dep(self) -> None:
        extra = self._p("extra")
        node = Add(a=self._p("a"), b=self._p("b"), extra=extra, _config=KnotConfig(id="add"))
        self.assertIn("extra", node.parents)

    def test_knot_id_property(self) -> None:
        node = Add(a=self._p("a"), b=self._p("b"), _config=KnotConfig(id="my-id"))
        self.assertEqual(node.knot_id, "my-id")

    def test_config_property(self) -> None:
        cfg = KnotConfig(id="add", description="test")
        node = Add(a=self._p("a"), b=self._p("b"), _config=cfg)
        self.assertIs(node.config, cfg)

    def test_input_names(self) -> None:
        node = Add(a=self._p("a"), b=self._p("b"), _config=KnotConfig(id="add"))
        self.assertIn("a", node.input_names)
        self.assertIn("b", node.input_names)

    def test_plain_knot_is_not_optional(self) -> None:
        from pirn.core.optional import Optional

        node = Add(a=self._p("a"), b=self._p("b"), _config=KnotConfig(id="add"))
        self.assertNotIsInstance(node, Optional)

    def test_immutability_after_construction(self) -> None:
        node = Add(a=self._p("a"), b=self._p("b"), _config=KnotConfig(id="add"))
        with self.assertRaisesRegex(AttributeError, "immutable"):
            node.new_attr = 42  # type: ignore[attr-defined]

    def test_repr(self) -> None:
        node = Add(a=self._p("a"), b=self._p("b"), _config=KnotConfig(id="add"))
        self.assertIn("Add", repr(node))
        self.assertIn("add", repr(node))

    def test_hash_is_identity_based(self) -> None:
        p = self._p("a")
        q = self._p("b")
        node1 = Add(a=p, b=q, _config=KnotConfig(id="n1"))
        node2 = Add(a=p, b=q, _config=KnotConfig(id="n2"))
        self.assertNotEqual(hash(node1), hash(node2))
        self.assertNotEqual(node1, node2)
        self.assertEqual(node1, node1)

    def test_tapestry_self_registration(self) -> None:
        with Tapestry() as t:
            p = self._p("a")
            q = self._p("b")
            Add(a=p, b=q, _config=KnotConfig(id="add"))
        ids = sorted(k.knot_id for k in t.all_knots())
        self.assertIn("add", ids)

    def test_process_raises_not_implemented_on_base(self) -> None:
        class NoImpl(Knot):
            async def process(self, **_: Any) -> Any:
                return await super().process(**_)

        node = NoImpl(_config=KnotConfig(id="noim"))
        with self.assertRaises(NotImplementedError):
            asyncio.run(node.process())


class TestKnotCall(unittest.TestCase):
    def test_call_returns_ok_on_success(self) -> None:
        from pirn.core.ok import Ok

        node = Add(
            a=Parameter("a", int, _config=KnotConfig(id="a")),
            b=Parameter("b", int, _config=KnotConfig(id="b")),
            _config=KnotConfig(id="add"),
        )
        result = asyncio.run(node({"a": 3, "b": 4}))
        self.assertIsInstance(result, Ok)
        self.assertEqual(result.value, 7)

    def test_call_returns_err_on_exception(self) -> None:
        from pirn.core.err import Err

        class Boom(Knot):
            async def process(self, **_: Any) -> Any:
                raise RuntimeError("boom")

        node = Boom(_config=KnotConfig(id="boom"))
        result = asyncio.run(node({}))
        self.assertIsInstance(result, Err)

    def test_call_with_validate_io_false_skips_validation(self) -> None:
        from pirn.core.ok import Ok

        node = Add(
            a=Parameter("a", int, _config=KnotConfig(id="a")),
            b=Parameter("b", int, _config=KnotConfig(id="b")),
            _config=KnotConfig(id="add", validate_io=False),
        )
        result = asyncio.run(node({"a": 1, "b": 2}))
        self.assertIsInstance(result, Ok)


class TestKnotSubclassValidation(unittest.TestCase):
    def test_process_with_args_raises_type_error(self) -> None:
        with self.assertRaisesRegex(TypeError, "may not declare \\*args"):

            class Bad(Knot):
                async def process(self, *args: Any, **_: Any) -> Any:
                    pass

    def test_process_without_var_keyword_raises(self) -> None:
        with self.assertRaisesRegex(TypeError, "must include"):

            class Bad(Knot):
                async def process(self, x: int) -> int:
                    return x

    def test_dynamic_process_signature_permits_args_on_that_class(self) -> None:
        """An abstract mid-tree base may declare the gradual parameter form.

        ``*args`` in a ``process`` declaration is a typing device that keeps a
        type checker from flagging every concrete knot's named inputs as an
        incompatible override (PIR-833). A base that opts in gets it; nothing
        about how the engine calls ``process`` changes.
        """

        class GradualBase(Knot):
            _dynamic_process_signature = True

            async def process(self, *args: Any, **kwargs: Any) -> int:
                raise NotImplementedError

        self.assertTrue(GradualBase._dynamic_process_signature)

    def test_dynamic_process_signature_is_not_inherited(self) -> None:
        """The opt-in is read from the class itself, never from the MRO.

        Otherwise one opted-in base would silently license ``*args`` in every
        concrete knot beneath it — exactly the author error the guard exists
        to catch.
        """

        class GradualBase(Knot):
            _dynamic_process_signature = True

            async def process(self, *args: Any, **kwargs: Any) -> int:
                raise NotImplementedError

        with self.assertRaisesRegex(TypeError, "may not declare \\*args"):

            class Concrete(GradualBase):
                async def process(self, *args: Any, **_: Any) -> int:
                    return 1


class TestKnotInitSteps(unittest.TestCase):
    """Each private step __init__ delegates to is independently testable."""

    def test_extract_framework_kwargs_requires_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "requires _config"):
            Add._extract_framework_kwargs({"a": 1, "b": 2})

    def test_extract_framework_kwargs_rejects_wrong_config_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a KnotConfig instance"):
            Add._extract_framework_kwargs({"_config": object()})

    def test_extract_framework_kwargs_splits_reserved_names(self) -> None:
        config = KnotConfig(id="x")
        result_config, tapestry, remaining = Add._extract_framework_kwargs(
            {"_config": config, "tapestry": None, "a": 1, "b": 2}
        )
        self.assertIs(result_config, config)
        self.assertIsNone(tapestry)
        self.assertEqual(remaining, {"a": 1, "b": 2})

    def test_extract_map_markers_no_markers_is_passthrough(self) -> None:
        config = KnotConfig(id="x")
        mapped, resolved = Add._extract_map_markers({"a": 1, "b": 2}, config)
        self.assertEqual(mapped, {})
        self.assertEqual(resolved, {"a": 1, "b": 2})

    def test_validate_kwargs_against_signature_missing_input(self) -> None:
        config = KnotConfig(id="x")
        with self.assertRaisesRegex(TypeError, "missing required"):
            Add._validate_kwargs_against_signature({"a": 1}, {"a", "b"}, False, config)

    def test_validate_kwargs_against_signature_unknown_kwarg_no_implicit(self) -> None:
        config = KnotConfig(id="x")
        with self.assertRaisesRegex(TypeError, "unknown kwarg"):
            Add._validate_kwargs_against_signature(
                {"a": 1, "b": 2, "c": 3}, {"a", "b"}, False, config
            )

    def test_validate_kwargs_against_signature_ok(self) -> None:
        config = KnotConfig(id="x")
        # Should not raise.
        Add._validate_kwargs_against_signature({"a": 1, "b": 2}, {"a", "b"}, False, config)

    def test_partition_parents_and_config(self) -> None:
        with Tapestry():
            source = Add(a=1, b=2, _config=KnotConfig(id="src"))
        parents, config_values = Knot._partition_parents_and_config({"parent": source, "scalar": 5})
        self.assertEqual(parents, {"parent": source})
        self.assertEqual(config_values, {"scalar": 5})

    def test_coerce_scalar_parameters_no_coercible_params_is_passthrough(self) -> None:
        config = KnotConfig(id="x")
        result = Add._coerce_scalar_parameters({"a": 1, "b": 2}, config, None)
        self.assertEqual(result, {"a": 1, "b": 2})


class TestGetTypeHintsFailureWarns(unittest.TestCase):
    """core/knot.py:179,561 — an unresolvable annotation must warn, not silently

    disable coercion/validation for the whole class.
    """

    def test_unresolvable_process_annotation_warns_when_coercion_is_first_needed(self) -> None:
        # Hints resolve on first need, never at class creation (PIR-872): a class
        # whose annotations name a TYPE_CHECKING-only type must still import.
        class _BadHint(Knot):
            async def process(self, x: _DoesNotExist, **_: Any) -> int:  # noqa: F821
                return 1

        with self.assertWarnsRegex(UserWarning, "get_type_hints\\(\\) failed"):
            _BadHint._coercible_params()

    def test_unresolvable_process_annotation_warns_when_adapters_are_built(self) -> None:
        class _BadHintForAdapters(Knot):
            async def process(self, x: int, **_: Any) -> int:
                return x

        # Corrupt the annotation after class creation so _build_adapters hits
        # the failure at construction time.
        _BadHintForAdapters.process.__annotations__["x"] = "_StillDoesNotExist"

        with self.assertWarnsRegex(UserWarning, "get_type_hints\\(\\) failed"):
            _BadHintForAdapters(
                x=Parameter("x", int, _config=KnotConfig(id="p")),
                _config=KnotConfig(id="bad"),
            )
