"""``_ValueShape`` — ``TypeGuard`` narrowers for runtime-bound container inputs.

Knot inputs arrive typed ``Any`` and the house style validates them with an
explicit ``isinstance`` check before use. A plain ``isinstance`` narrows
``Any`` to ``dict[Unknown, Unknown]`` / ``Sequence[Unknown]`` under pyright
strict, which then leaks ``Unknown`` into every loop and call that follows.
These guards *are* the same runtime check, but carry the element types the
check implies, so the validated value is fully typed afterwards without a
``typing.cast`` (which the Python conventions forbid on non-primitives).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard


class _ValueShape:  # pyright: ignore[reportUnusedClass]  # imported by the quality, sources, transforms and validation knots
    """The ``isinstance`` checks for runtime-bound container inputs, typed."""

    @staticmethod
    def is_mapping(value: object) -> TypeGuard[Mapping[Any, Any]]:
        """``isinstance(value, Mapping)``, narrowing to ``Mapping[Any, Any]``."""
        return isinstance(value, Mapping)

    @staticmethod
    def is_str_mapping(value: object) -> TypeGuard[dict[str, Any]]:
        """``isinstance(value, dict)``, narrowing to ``dict[str, Any]``."""
        return isinstance(value, dict)

    @staticmethod
    def is_sequence(value: object) -> TypeGuard[Sequence[Any]]:
        """``isinstance(value, Sequence)``, narrowing to ``Sequence[Any]``."""
        return isinstance(value, Sequence)

    @staticmethod
    def is_tuple(value: object) -> TypeGuard[tuple[Any, ...]]:
        """``isinstance(value, tuple)``, narrowing to ``tuple[Any, ...]``."""
        return isinstance(value, tuple)
