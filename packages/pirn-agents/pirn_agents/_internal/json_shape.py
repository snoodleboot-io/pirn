"""``JsonShape`` — typed ``isinstance`` narrowers for JSON-shaped values.

A decoded JSON payload (a provider response, a message dict, a tool argument
map) arrives as ``Any``; a bare ``isinstance(value, Mapping)`` narrows it to
``Mapping[Unknown, Unknown]``, which strict pyright rejects at every subsequent
``.get`` / index. These ``TypeGuard`` helpers are the same runtime check with
the element types the JSON contract promises, so call sites narrow without
``typing.cast`` (which the house style forbids on non-primitives).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard


class JsonShape:
    """TypeGuard narrowers for JSON-shaped values: the isinstance check, typed."""

    @staticmethod
    def is_mapping(value: object) -> TypeGuard[Mapping[str, Any]]:
        """Return ``True`` when ``value`` is any ``Mapping`` (string keys assumed)."""
        return isinstance(value, Mapping)

    @staticmethod
    def is_any_mapping(value: object) -> TypeGuard[Mapping[Any, Any]]:
        """Return ``True`` when ``value`` is any ``Mapping``, keys of any type."""
        return isinstance(value, Mapping)

    @staticmethod
    def is_dict(value: object) -> TypeGuard[dict[str, Any]]:
        """Return ``True`` when ``value`` is a plain ``dict`` (string keys assumed)."""
        return isinstance(value, dict)

    @staticmethod
    def is_list(value: object) -> TypeGuard[list[Any]]:
        """Return ``True`` when ``value`` is a ``list``."""
        return isinstance(value, list)

    @staticmethod
    def is_tuple(value: object) -> TypeGuard[tuple[Any, ...]]:
        """Return ``True`` when ``value`` is a ``tuple``."""
        return isinstance(value, tuple)

    @staticmethod
    def is_list_or_tuple(value: object) -> TypeGuard[list[Any] | tuple[Any, ...]]:
        """Return ``True`` when ``value`` is a ``list`` or a ``tuple``."""
        return isinstance(value, (list, tuple))

    @staticmethod
    def is_sequence(value: object) -> TypeGuard[Sequence[Any]]:
        """Return ``True`` when ``value`` is any ``Sequence`` (``str`` included)."""
        return isinstance(value, Sequence)
