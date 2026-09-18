"""A knot whose ``process()`` hints cannot resolve is refused, not silently unvalidated.

``Knot`` used to warn and carry on with no hints at all when
``typing.get_type_hints`` failed, which turned ``KnotConfig.validate_io`` into a
no-op and disabled ``Knot | T`` scalar coercion for every instance of the class.
These tests pin the raise, and pin that ``KnotFactory`` generates a ``process``
whose own annotations resolve even when the callable it wraps carries neither
annotations nor ``__globals__`` (PIR-873).
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.parameter import Parameter
from pirn.exceptions.unresolved_annotation_error import UnresolvedAnnotationError


class _UnresolvableHint(Knot):
    """Its ``process()`` names a type that exists in no namespace it can reach."""

    async def process(self, value: NoSuchTypeAnywhere, **_: Any) -> int:  # noqa: F821
        return 1


class _CoercibleUnresolvable(Knot):
    """Its ``Knot | T`` hint names an unreachable type, so coercion cannot be read."""

    async def process(self, value: Knot | NoSuchTypeAnywhere, **_: Any) -> int:  # noqa: F821
        return 1


class _Thunk:
    """A callable object: function-shaped attributes, no annotations, no ``__globals__``."""

    def __init__(self, value: Any) -> None:
        self._value = value
        self.__name__ = "thunk"
        self.__qualname__ = "thunk"
        self.__doc__ = "Return a fixed value."

    def __call__(self) -> Any:
        return self._value


class TestUnresolvableProcessHints(unittest.TestCase):
    def test_construction_raises_instead_of_warning(self) -> None:
        # Act / Assert.
        with self.assertRaises(UnresolvedAnnotationError) as caught:
            _UnresolvableHint(value=1, _config=KnotConfig(id="bad"))

        # Assert: the message names the class, so the author knows which knot.
        self.assertEqual(caught.exception.knot_class, "_UnresolvableHint")

    def test_the_error_is_catchable_as_a_type_error(self) -> None:
        # Act / Assert: a broken declared type is a typing failure.
        with self.assertRaises(TypeError):
            _UnresolvableHint(value=1, _config=KnotConfig(id="bad2"))

    def test_reading_coercible_params_raises(self) -> None:
        # Act / Assert: the second resolution site raises too, so a ``Knot | T``
        # input is never silently left uncoerced.
        with self.assertRaises(UnresolvedAnnotationError):
            _CoercibleUnresolvable.input_annotations()

    def test_a_resolvable_knot_still_constructs(self) -> None:
        # Arrange / Act.
        knot = Parameter("p", int, default=1, _config=KnotConfig(id="p"))

        # Assert.
        self.assertEqual(knot.knot_id, "p")


class TestKnotFactoryGeneratedAnnotations(unittest.IsolatedAsyncioTestCase):
    def test_a_globals_less_callable_yields_resolvable_hints(self) -> None:
        # Arrange.
        knot_class = KnotFactory.create(_Thunk(7)).knot_class

        # Act: this used to raise ``NameError`` inside ``get_type_hints`` --
        # resolution walked to the thunk, which has no ``__globals__``.
        hints = knot_class._process_hints(knot_class._process_signature())

        # Assert: the generated method's own annotations are objects already.
        self.assertIs(hints["self"], Knot)
        self.assertIs(hints["return"], Any)

    async def test_a_globals_less_callable_still_runs(self) -> None:
        # Arrange.
        knot = KnotFactory.create(_Thunk(7)).knot_class(_config=KnotConfig(id="thunk"))

        # Act.
        result = await knot({})

        # Assert.
        self.assertEqual(getattr(result, "value", None), 7)

    def test_a_real_functions_own_hints_are_left_alone(self) -> None:
        # Arrange.
        @KnotFactory.knot
        async def scale(value: int, factor: int = 2) -> int:
            return value * factor

        # Act.
        annotations = scale.knot_class.input_annotations()

        # Assert: the wrapped function's contract, not the wrapper's.
        self.assertEqual(annotations, {"value": int, "factor": int})
