"""``PyarrowRename`` — Tier-2 column-rename knot dispatching to
:meth:`pyarrow.Table.rename_columns`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowRename(Knot):
    """Apply an old → new column name mapping using PyArrow's native rename."""

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
        batch: PyarrowDataBatch,
        mapping: Any,  # Mapping[str, str] — deferred; custom errors fire in process(), not pydantic
        **_: Any,
    ) -> PyarrowDataBatch:
        """Rename columns in the table according to the configured mapping.

        Args:
            batch: The upstream PyarrowDataBatch whose columns will be renamed.
            mapping: Old-name → new-name pairs; columns absent from the mapping
                are left unchanged.

        Returns:
            A new PyarrowDataBatch with the applicable columns renamed.
        """
        if not isinstance(mapping, Mapping) or not mapping:
            raise TypeError(
                "PyarrowRename: mapping must be a non-empty Mapping[old_name, new_name]"
            )
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                raise TypeError(
                    "PyarrowRename: mapping keys and values must be non-empty strings"
                )
        # PyArrow's rename_columns takes a positional list parallel to the
        # current column order (no skipping). Build that list explicitly,
        # leaving columns absent from the mapping unchanged.
        new_names = [
            mapping.get(name, name) for name in batch.table.column_names
        ]
        if new_names == list(batch.table.column_names):
            return batch
        return batch.with_table(batch.table.rename_columns(new_names))
