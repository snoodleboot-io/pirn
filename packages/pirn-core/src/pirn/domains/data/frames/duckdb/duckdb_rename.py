"""``DuckdbRename`` — Tier-2 column-rename knot dispatching to a
``SELECT col AS new_col, ...`` projection.

DuckDB's relation API does not expose a simple ``rename`` method. The
cleanest stable approach is to project: build a SQL fragment of the form
``SELECT a AS x, b AS y, c, d`` (preserving columns not in the mapping)
and run it through ``relation.project(...)``.

Column names from the upstream relation are validated to be plain
identifiers before being interpolated, so this knot is safe against
upstream data exfiltration via crafted column names.

Algorithm:
    1. Validate ``mapping`` as a non-empty ``Mapping[str, str]``.
    2. Reject entries whose keys or values contain forbidden identifier
       tokens (``"``, ``\\``, ``;``, ``--``, ``/*``, ``*/``, ``'``).
    3. Filter to entries whose keys exist in the upstream relation; if
       none apply, return the batch unchanged.
    4. Validate every upstream column name as a plain identifier before
       interpolation.
    5. For each column, emit either ``"old" AS "new"`` or ``"col"``
       (pass-through), then call ``relation.project(fragments)`` and
       return the result.

    ```text
    applicable = {old: new for old, new in mapping if old in columns}
    fragments  = ['"old" AS "new"' if old in applicable else '"col"'
                  for col in columns]
    return relation.project(", ".join(fragments))
    ```

References:
    [1] DuckDB Python API — DuckDBPyRelation.project:
        https://duckdb.org/docs/api/python/relational_api
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch
from pirn.domains.data.identifier_validator import IdentifierValidator


class DuckdbRename(Knot):
    """Apply an old → new column name mapping using a DuckDB projection."""

    def __init__(
        self,
        *,
        batch: Knot,
        mapping: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, mapping=mapping, _config=_config, **kwargs)

    async def process(
        self,
        batch: DuckdbDataBatch,
        mapping: Any,
        **_: Any,
    ) -> DuckdbDataBatch:
        """Rename columns in the batch according to the configured mapping and return the result.

        Args:
            batch: The DuckdbDataBatch whose columns are to be renamed.
            mapping: A non-empty mapping of old column name to new column name.

        Returns:
            A new DuckdbDataBatch with the applicable columns renamed.
        """
        if not isinstance(mapping, Mapping) or not mapping:
            raise TypeError("DuckdbRename: mapping must be a non-empty Mapping[old_name, new_name]")
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                raise TypeError("DuckdbRename: mapping keys and values must be non-empty strings")
            self._reject_unsafe_identifier("mapping key", old)
            self._reject_unsafe_identifier("mapping value", new)
        applicable = {old: new for old, new in mapping.items() if old in batch.relation.columns}
        if not applicable:
            return batch
        # Validate every column name we're about to interpolate. Upstream
        # column names could in principle be crafted; refuse anything that
        # is not a bare identifier.
        for column in batch.relation.columns:
            IdentifierValidator.validate_column("DuckdbRename: upstream column", column)
        fragments: list[str] = []
        for column in batch.relation.columns:
            if column in applicable:
                fragments.append(f'"{column}" AS "{applicable[column]}"')
            else:
                fragments.append(f'"{column}"')
        projected = batch.relation.project(", ".join(fragments))
        return batch.with_relation(projected)

    @staticmethod
    def _reject_unsafe_identifier(label: str, value: str) -> None:
        # Identifier-slot injection red flags. We're putting the names
        # inside double-quoted identifier slots; double-quotes and
        # backslashes can escape that, and the standard SQL injection
        # tokens are an obvious red flag regardless of context.
        forbidden = ('"', "\\", ";", "--", "/*", "*/", "'")
        for token in forbidden:
            if token in value:
                raise ValueError(
                    f"DuckdbRename: {label} {value!r} contains forbidden token {token!r}"
                )
