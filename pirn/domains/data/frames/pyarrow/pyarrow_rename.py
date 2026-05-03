"""``PyarrowRename`` — Tier-2 column-rename knot dispatching to
:meth:`pyarrow.Table.rename_columns`.
"""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowRename(Knot):
    """Apply an old → new column name mapping using PyArrow's native rename."""

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
                "PyarrowRename: mapping must be a non-empty Mapping[old_name, new_name]"
            )
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                raise TypeError(
                    "PyarrowRename: mapping keys and values must be non-empty strings"
                )
        self._mapping: dict[str, str] = dict(mapping)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def mapping(self) -> Mapping[str, str]:
        return dict(self._mapping)

    async def process(self, batch: PyarrowDataBatch, **_: Any) -> PyarrowDataBatch:
        """Rename columns in the table according to the configured mapping and return the result.

        Args:
            batch: The upstream PyarrowDataBatch whose columns will be renamed.

        Returns:
            A new PyarrowDataBatch with the applicable columns renamed.
        """
        # PyArrow's rename_columns takes a positional list parallel to the
        # current column order (no skipping). Build that list explicitly,
        # leaving columns absent from the mapping unchanged.
        new_names = [
            self._mapping.get(name, name) for name in batch.table.column_names
        ]
        if new_names == list(batch.table.column_names):
            return batch
        return batch.with_table(batch.table.rename_columns(new_names))
