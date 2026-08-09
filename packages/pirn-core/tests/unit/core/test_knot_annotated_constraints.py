"""A knot may state a value domain in its signature, and the engine enforces it.

``validate_io`` builds a pydantic ``TypeAdapter`` per named ``process``
parameter, which covers *types* — ``str`` rejects ``123``, an interface rejects
an unrelated object. It could not cover *domains*: "a positive int", "a
non-empty string". Those are expressible only as ``Annotated[int,
Field(gt=0)]``, and :func:`typing.get_type_hints` erases ``Annotated`` extras
unless asked not to, so the constraint reached pydantic as a bare ``int`` and
was silently dropped — validation that read as declared but never ran.

That is the framework-level way to say "this input must be positive", and it
has to work before per-knot ``isinstance``/``ValueError`` re-guards can be
removed in favour of it (PIR-734). These tests pin it.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Annotated, Any

from pydantic import Field

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.parameter import Parameter


class Bounded(Knot):
    """Declares its domain in the signature rather than re-checking in the body."""

    async def process(self, top_k: Annotated[int, Field(gt=0)], **_: Any) -> int:
        return top_k


class NonEmpty(Knot):
    async def process(self, query: Annotated[str, Field(min_length=1)], **_: Any) -> str:
        return query


class TestAnnotatedInputConstraints(unittest.TestCase):
    def test_a_value_inside_the_domain_passes(self) -> None:
        # Arrange
        knot = Bounded(
            top_k=Parameter("top_k", int, _config=KnotConfig(id="k")),
            _config=KnotConfig(id="bounded"),
        )

        # Act
        result = asyncio.run(knot({"top_k": 3}))

        # Assert
        assert isinstance(result, Ok)
        assert result.value == 3

    def test_a_value_outside_the_domain_is_rejected(self) -> None:
        """The constraint is enforced, not decoration."""
        # Arrange
        knot = Bounded(
            top_k=Parameter("top_k", int, _config=KnotConfig(id="k")),
            _config=KnotConfig(id="bounded"),
        )

        # Act
        result = asyncio.run(knot({"top_k": 0}))

        # Assert
        assert isinstance(result, Err)

    def test_a_string_domain_is_enforced_too(self) -> None:
        # Arrange
        knot = NonEmpty(
            query=Parameter("query", str, _config=KnotConfig(id="q")),
            _config=KnotConfig(id="nonempty"),
        )

        # Act / Assert
        assert isinstance(asyncio.run(knot({"query": ""})), Err)
        assert isinstance(asyncio.run(knot({"query": "hi"})), Ok)

    def test_the_constraint_is_checked_eagerly_for_a_constant(self) -> None:
        """A constant is known at construction, so it fails there, not at run."""
        # Act / Assert
        with self.assertRaises(TypeError) as caught:
            Bounded(top_k=-1, _config=KnotConfig(id="bounded"))

        assert "failed validation" in str(caught.exception)

    def test_a_constant_inside_the_domain_constructs(self) -> None:
        assert Bounded(top_k=7, _config=KnotConfig(id="bounded")) is not None

    def test_validate_io_false_still_opts_out(self) -> None:
        """Constraints ride on validation; turning it off turns them off."""
        # Arrange / Act
        knot = Bounded(top_k=-1, _config=KnotConfig(id="bounded", validate_io=False))

        # Assert
        assert isinstance(asyncio.run(knot({"top_k": -1})), Ok)


if __name__ == "__main__":
    unittest.main()
