"""``ShapeGuard`` — ``TypeGuard`` narrowers for values whose shape is only known at runtime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeGuard


class ShapeGuard:
    """Runtime shape checks that carry the element types they establish.

    A plain ``isinstance(value, dict)`` on an ``object`` (a decoded JSON
    payload, a runtime-bound knot input) narrows to ``dict[Unknown, Unknown]``
    under pyright strict, which then leaks ``Unknown`` into every loop and call
    that follows.  Each guard here performs the check the name promises and
    narrows to element types of ``object``, so the caller keeps narrowing the
    elements it actually uses instead of trusting a ``cast``.
    """

    @staticmethod
    def is_dict(value: object) -> TypeGuard[dict[object, object]]:
        """Whether ``value`` is a ``dict``, narrowing its keys and values to ``object``."""
        return isinstance(value, dict)

    @staticmethod
    def is_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
        """Whether ``value`` is a ``Mapping``, narrowing its keys and values to ``object``."""
        return isinstance(value, Mapping)

    @staticmethod
    def is_str_keyed_dict(value: object) -> TypeGuard[dict[str, object]]:
        """Whether ``value`` is a ``dict`` whose every key is a ``str``.

        Args:
            value: Any runtime value.

        Returns:
            ``True`` for a ``dict`` with only string keys (every decoded JSON
            object), ``False`` otherwise.
        """
        return ShapeGuard.is_dict(value) and all(isinstance(key, str) for key in value)

    @staticmethod
    def is_str_keyed_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
        """Whether ``value`` is a ``Mapping`` whose every key is a ``str``.

        Args:
            value: Any runtime value.

        Returns:
            ``True`` for a mapping with only string keys, ``False`` otherwise.
        """
        return ShapeGuard.is_mapping(value) and all(isinstance(key, str) for key in value)

    @staticmethod
    def is_list(value: object) -> TypeGuard[list[object]]:
        """Whether ``value`` is a ``list``, narrowing its elements to ``object``."""
        return isinstance(value, list)

    @staticmethod
    def is_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
        """Whether ``value`` is a ``tuple``, narrowing its elements to ``object``."""
        return isinstance(value, tuple)
