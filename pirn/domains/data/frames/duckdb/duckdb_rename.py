"""``DuckdbRename`` — Tier-2 column-rename knot dispatching to a
``SELECT col AS new_col, ...`` projection.

DuckDB's relation API does not expose a simple ``rename`` method. The
cleanest stable approach is to project: build a SQL fragment of the form
``SELECT a AS x, b AS y, c, d`` (preserving columns not in the mapping)
and run it through ``relation.project(...)``.

Column names from the upstream relation are validated to be plain
identifiers before being interpolated, so this knot is safe against
upstream data exfiltration via crafted column names.
"""

from __future__ import annotations

from typing import Any, Mapping

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
        mapping: Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(mapping, Mapping) or not mapping:
            raise TypeError(
                "DuckdbRename: mapping must be a non-empty Mapping[old_name, new_name]"
            )
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                raise TypeError(
                    "DuckdbRename: mapping keys and values must be non-empty strings"
                )
            self._reject_unsafe_identifier("mapping key", old)
            self._reject_unsafe_identifier("mapping value", new)
        self._mapping: dict[str, str] = dict(mapping)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def mapping(self) -> Mapping[str, str]:
        return dict(self._mapping)

    async def process(self, batch: DuckdbDataBatch, **_: Any) -> DuckdbDataBatch:
        """Rename columns in the batch according to the configured mapping and return the result.

        Args:
            batch: The DuckdbDataBatch whose columns are to be renamed.

        Returns:
            A new DuckdbDataBatch with the applicable columns renamed.
        """
        applicable = {
            old: new for old, new in self._mapping.items()
            if old in batch.relation.columns
        }
        if not applicable:
            return batch
        # Validate every column name we're about to interpolate. Upstream
        # column names could in principle be crafted; refuse anything that
        # is not a bare identifier.
        for column in batch.relation.columns:
            IdentifierValidator.validate_column(
                "DuckdbRename: upstream column", column
            )
        fragments: list[str] = []
        for column in batch.relation.columns:
            if column in applicable:
                fragments.append(f'"{column}" AS "{applicable[column]}"')
            else:
                fragments.append(f'"{column}"')
        projected = batch.relation.project(", ".join(fragments))
        return batch.with_relation(projected)

    def _reject_unsafe_identifier(self, label: str, value: str) -> None:
        # Identifier-slot injection red flags. We're putting the names
        # inside double-quoted identifier slots; double-quotes and
        # backslashes can escape that, and the standard SQL injection
        # tokens are an obvious red flag regardless of context.
        forbidden = ('"', "\\", ";", "--", "/*", "*/", "'")
        for token in forbidden:
            if token in value:
                raise ValueError(
                    f"DuckdbRename: {label} {value!r} contains forbidden "
                    f"token {token!r}"
                )
