"""Shared identifier-validation helper for tabular transform knots.

Aggregations, joins, casts and renames all need to confirm that
caller-supplied column names are plain SQL/Python identifiers before
splicing them into expressions. The same regex was previously copy-
pasted into every transform; this class centralises it.

The accepted form is the conservative subset used by SQL engines and
Python attribute access alike: a leading letter or underscore followed
by letters, digits or underscores. No quoting, no spaces, no dots.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import ClassVar


class IdentifierValidator:
    """Validate column / identifier names against a strict regex."""

    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    @classmethod
    def validate_column(cls, label: str, name: str) -> None:
        """Raise if ``name`` is not a plain identifier.

        ``label`` names the offending parameter for the error message
        (e.g. ``"by"``, ``"left_on"``, ``"output column"``). The label
        is interpolated into the raised :class:`ValueError`.
        """
        if not isinstance(name, str) or not name:
            raise TypeError(f"{label}: must be a non-empty string")
        if not cls._pattern.match(name):
            raise ValueError(
                f"{label}: {name!r} is not a plain identifier ([A-Za-z_][A-Za-z0-9_]*)"
            )

    @classmethod
    def validate_columns(cls, label: str, names: Sequence[str]) -> None:
        """Validate every entry in ``names`` against :meth:`validate_column`.

        ``label`` is suffixed with the index of any failing entry so
        callers can identify which element of a multi-column parameter
        was rejected.
        """
        if not isinstance(names, Sequence) or isinstance(names, (str, bytes)):
            raise TypeError(f"{label}: must be a sequence of column names")
        if not names:
            raise ValueError(f"{label}: must be non-empty")
        for index, name in enumerate(names):
            cls.validate_column(f"{label}[{index}]", name)
