"""``ColumnHasher`` — hash specified columns for anonymisation or join keys.

Each named column is replaced with a hex-digest hash of the UTF-8 encoded
string representation of its value.  The original column value is
overwritten; downstream knots see only the digest.

Algorithm:
    1. Receive resolved ``rows``, ``columns``, and ``algorithm`` in
       ``process()``.
    2. Validate column identifiers and algorithm membership.
    3. For each row, for each target column, hash the value with the
       chosen algorithm and overwrite the column value with the hex digest.
    4. Return the enriched row list.

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

import hashlib
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class ColumnHasher(Knot):
    """Replace column values with their cryptographic hash digests."""

    def __init__(
        self,
        *,
        rows: Knot | list,
        columns: Knot | tuple[str, ...],
        algorithm: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            columns=columns,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _hash(value: Any, algorithm: str) -> str:
        raw = str(value).encode("utf-8")
        h = hashlib.new(algorithm, raw, usedforsecurity=False)
        return h.hexdigest()

    async def process(
        self,
        *,
        rows: Any,
        columns: Any,
        algorithm: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        col_tuple = tuple(columns)
        IdentifierValidator.validate_columns("columns", col_tuple)
        if algorithm not in ("sha256", "md5"):
            raise ValueError("ColumnHasher: algorithm must be 'sha256' or 'md5'")
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            for col in col_tuple:
                if col in new_row:
                    new_row[col] = self._hash(new_row[col], algorithm)
            result.append(new_row)
        return result
