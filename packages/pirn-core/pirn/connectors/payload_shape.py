"""``PayloadShape`` — narrow untyped connector payloads to precise shapes.

Vendor SDKs, ``json`` decoders and optional-dependency readers hand the
connectors values whose static type is ``Any`` or ``object``. This class is
the home for the connector-specific shape checks (``Iterable``, numpy
``ndarray``) and for the strict record extractor used by the SaaS, BI /
catalog and observability clients. The general ``dict`` / ``Mapping`` /
``list`` guards live on :class:`pirn.core.shape_guard.ShapeGuard`, which
inspects keys rather than trusting them.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, TypeGuard

from pirn.core.shape_guard import ShapeGuard

if TYPE_CHECKING:
    import numpy.typing as npt


class PayloadShape:
    """Type guards and record extraction for untyped connector payloads."""

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

    @staticmethod
    def rows(value: object, *, source: str) -> list[Mapping[str, Any]]:
        """Materialise a response's record collection as a list of rows (strict).

        Args:
            value: The record collection taken from a response. A missing or
                empty collection (any falsy value) yields no rows.
            source: Name prefixed to the error message (e.g. ``"JiraClient"``).

        Returns:
            The records, in response order.

        Raises:
            ValueError: If ``value`` is not a ``list``/``tuple`` or holds an
                element that is not a ``Mapping`` whose every key is a ``str``.
                A malformed row is never dropped: a page that silently loses
                records is worse than one that fails.
        """
        if not value:
            return []
        if ShapeGuard.is_list_or_tuple(value):
            rows: list[Mapping[str, Any]] = []
            for item in value:
                if not ShapeGuard.is_str_keyed_mapping(item):
                    raise ValueError(
                        f"{source}: expected every record to be a mapping with only "
                        f"string keys; got {type(item).__name__}"
                    )
                rows.append(item)
            return rows
        raise ValueError(f"{source}: expected a list of records; got {type(value).__name__}")
