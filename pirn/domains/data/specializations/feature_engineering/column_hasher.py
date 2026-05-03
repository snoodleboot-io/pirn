"""``ColumnHasher`` — hash specified columns for anonymisation or join keys.

Each named column is replaced with a hex-digest hash of the UTF-8 encoded
string representation of its value.  The original column value is
overwritten; downstream knots see only the digest.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class ColumnHasher(Knot):
    """Replace column values with their cryptographic hash digests."""

    def __init__(
        self,
        *,
        rows: Knot,
        columns: Sequence[str],
        algorithm: Literal["sha256", "md5"] = "sha256",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        col_tuple = tuple(columns)
        IdentifierValidator.validate_columns("columns", col_tuple)
        if algorithm not in ("sha256", "md5"):
            raise ValueError(
                "ColumnHasher: algorithm must be 'sha256' or 'md5'"
            )
        self._columns = col_tuple
        self._algorithm = algorithm
        super().__init__(rows=rows, _config=_config, **kwargs)

    def _hash(self, value: Any) -> str:
        raw = str(value).encode("utf-8")
        h = hashlib.new(self._algorithm, raw)
        return h.hexdigest()

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Replace each target column's value with its hash digest.

        Args:
            rows: Upstream rows as a list of dicts.

        Returns:
            Rows with target columns replaced by hex-digest strings.
        """
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            for col in self._columns:
                if col in new_row:
                    new_row[col] = self._hash(new_row[col])
            result.append(new_row)
        return result
