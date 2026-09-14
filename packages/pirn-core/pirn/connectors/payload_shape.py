"""``PayloadShape`` — narrow untyped connector payloads to precise shapes.

Vendor SDKs, ``json`` decoders and optional-dependency readers hand the
connectors values whose static type is ``Any`` or ``object``. This class is
the single home for the runtime shape checks the connectors perform on such
values, turning them into precise ``object``-based shapes
(``Mapping[str, object]``, ``list[object]``, ``npt.NDArray[Any]``, ...) the
callers can read without leaking unknown types, plus the two record
extractors used by the SaaS and BI / catalog clients.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, TypeGuard

if TYPE_CHECKING:
    import numpy.typing as npt


class PayloadShape:
    """Type guards and record extraction for untyped connector payloads."""

    @staticmethod
    def is_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
        """Return whether ``value`` is any ``Mapping``."""
        return isinstance(value, Mapping)

    @staticmethod
    def is_str_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
        """Return whether ``value`` is a ``Mapping`` keyed by strings (a JSON object).

        Keys are not inspected: decoded JSON objects and SDK records are
        string-keyed by construction.
        """
        return isinstance(value, Mapping)

    @staticmethod
    def is_dict(value: object) -> TypeGuard[dict[object, object]]:
        """Return whether ``value`` is a ``dict``."""
        return isinstance(value, dict)

    @staticmethod
    def is_str_dict(value: object) -> TypeGuard[dict[str, object]]:
        """Return whether ``value`` is a ``dict`` keyed by strings (a decoded JSON object).

        Keys are not inspected: ``json`` always decodes object keys as strings.
        """
        return isinstance(value, dict)

    @staticmethod
    def is_list(value: object) -> TypeGuard[list[object]]:
        """Return whether ``value`` is a ``list`` (a decoded JSON array)."""
        return isinstance(value, list)

    @staticmethod
    def is_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
        """Return whether ``value`` is a ``tuple``."""
        return isinstance(value, tuple)

    @staticmethod
    def is_sequence(value: object) -> TypeGuard[list[object] | tuple[object, ...]]:
        """Return whether ``value`` is a ``list`` or a ``tuple``."""
        return isinstance(value, (list, tuple))

    @staticmethod
    def is_iterable(value: object) -> TypeGuard[Iterable[object]]:
        """Return whether ``value`` is any ``Iterable``."""
        return isinstance(value, Iterable)

    @staticmethod
    def is_ndarray(value: object) -> TypeGuard[npt.NDArray[Any]]:
        """Return whether ``value`` is a numpy ``ndarray``."""
        # numpy stays a lazy dependency (install-isolation gate): a value cannot be
        # an ndarray unless numpy has already been imported by whoever built it.
        numpy_module = sys.modules.get("numpy")
        if numpy_module is None:
            return False
        ndarray_type: type[object] = numpy_module.ndarray
        return isinstance(value, ndarray_type)

    @classmethod
    def rows(cls, value: object, *, source: str) -> list[Mapping[str, Any]]:
        """Materialise a response's record collection as a list of rows (strict).

        Args:
            value: The record collection taken from a response. A missing or
                empty collection (any falsy value) yields no rows.
            source: Name prefixed to the error message (e.g. ``"JiraClient"``).

        Returns:
            The records, in response order.

        Raises:
            ValueError: If ``value`` is not a ``list``/``tuple`` or holds an
                element that is not a ``Mapping``.
        """
        if not value:
            return []
        if cls.is_sequence(value):
            rows: list[Mapping[str, Any]] = []
            for item in value:
                if not cls.is_str_mapping(item):
                    raise ValueError(
                        f"{source}: expected every record to be a mapping; "
                        f"got {type(item).__name__}"
                    )
                rows.append(item)
            return rows
        raise ValueError(f"{source}: expected a list of records; got {type(value).__name__}")

    @classmethod
    def entities(cls, value: object) -> list[Mapping[str, Any]]:
        """Return the mapping elements of ``value`` when it is a list, else ``[]`` (lenient).

        Non-mapping elements are skipped: every catalog capability yields
        entity rows as ``Mapping[str, Any]``.
        """
        if not cls.is_list(value):
            return []
        return [item for item in value if cls.is_str_mapping(item)]
