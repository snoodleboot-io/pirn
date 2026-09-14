"""``_JsonShape`` — typed ``isinstance`` narrowers for JSON-shaped values.

A decoded JSON payload arrives as ``Any``; a bare ``isinstance(value, Mapping)``
narrows it to ``Mapping[Unknown, Unknown]``, which strict pyright rejects at
every subsequent ``.get`` / index. These ``TypeGuard`` helpers are the same
runtime check with the element types the JSON contract promises, so call sites
narrow without ``typing.cast`` (which the house style forbids on non-primitives).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeGuard


class _JsonShape:  # pyright: ignore[reportUnusedClass]  # imported by the JSON-consuming knots and connectors
    """TypeGuard narrowers for JSON-shaped values: the isinstance check, typed."""

    @staticmethod
    def is_mapping(value: object) -> TypeGuard[Mapping[str, Any]]:
        """Return ``True`` when ``value`` is any ``Mapping`` (string keys assumed)."""
        return isinstance(value, Mapping)

    @staticmethod
    def is_dict(value: object) -> TypeGuard[dict[str, Any]]:
        """Return ``True`` when ``value`` is a plain ``dict`` (string keys assumed)."""
        return isinstance(value, dict)

    @staticmethod
    def is_list(value: object) -> TypeGuard[list[Any]]:
        """Return ``True`` when ``value`` is a ``list``."""
        return isinstance(value, list)
