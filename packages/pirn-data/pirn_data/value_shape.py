"""``ValueShape`` — ``TypeGuard`` narrowers for runtime-bound container inputs.

Knot inputs arrive typed ``Any`` and the house style validates them with an
explicit ``isinstance`` check before use. A plain ``isinstance`` narrows
``Any`` to ``dict[Unknown, Unknown]`` / ``Sequence[Unknown]`` under pyright
strict, which then leaks ``Unknown`` into every loop and call that follows.
These guards *are* the same runtime check, but carry the element types the
check implies, so the validated value is fully typed afterwards without a
``typing.cast`` (which the Python conventions forbid on non-primitives).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, TypeGuard


class ValueShape:
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

    @staticmethod
    def is_list(value: object) -> TypeGuard[list[Any]]:
        """``isinstance(value, list)``, narrowing to ``list[Any]``."""
        return isinstance(value, list)

    @staticmethod
    def is_list_or_tuple(value: object) -> TypeGuard[list[Any] | tuple[Any, ...]]:
        """``isinstance(value, (list, tuple))``, narrowing to ``list[Any] | tuple[Any, ...]``."""
        return isinstance(value, (list, tuple))

    @staticmethod
    def is_iterable(value: object) -> TypeGuard[Iterable[Any]]:
        """``isinstance(value, Iterable)``, narrowing to ``Iterable[Any]``."""
        return isinstance(value, Iterable)

    @staticmethod
    def is_callable(value: object) -> TypeGuard[Callable[..., Any]]:
        """``callable(value)``, narrowing to ``Callable[..., Any]``.

        The builtin narrows to ``(...) -> object``, which rejects the result
        wherever a third-party engine expects its own expression type.
        """
        return callable(value)
