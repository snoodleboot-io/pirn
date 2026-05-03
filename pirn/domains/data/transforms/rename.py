"""``Rename`` — rename columns in a :class:`DataBatch` according to a
``Mapping[old_name, new_name]``.

Columns absent from the mapping pass through unchanged. The batch's
:class:`DataSchema` is updated so downstream consumers see the new names
in ``columns``, ``primary_keys``, and ``nullable``.
"""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema


class Rename(Knot):
    """Apply an old → new column name mapping to a :class:`DataBatch`."""

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
                "Rename: mapping must be a non-empty Mapping[old_name, new_name]"
            )
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str):
                raise TypeError(
                    "Rename: mapping keys and values must be strings"
                )
            if not old or not new:
                raise ValueError(
                    "Rename: mapping keys and values must be non-empty"
                )
        self._mapping: dict[str, str] = dict(mapping)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def mapping(self) -> Mapping[str, str]:
        return dict(self._mapping)

    async def process(self, batch: DataBatch, **_: Any) -> DataBatch:
        """Rename columns in each row according to the mapping and return the updated batch with an updated schema.

        Args:
            batch: The DataBatch whose column names will be remapped.

        Returns:
            A new DataBatch with columns renamed and the schema updated to reflect the new names.
        """
        new_rows = tuple(self._rename_row(row) for row in batch.rows)
        new_schema = self._rename_schema(batch.schema)
        return batch.with_rows(new_rows).with_schema(new_schema)

    def _rename_row(
        self, row: Mapping[str, Any]
    ) -> dict[str, Any]:
        return {self._mapping.get(k, k): v for k, v in row.items()}

    def _rename_schema(self, schema: DataSchema) -> DataSchema:
        new_columns = {
            self._mapping.get(name, name): expected_type
            for name, expected_type in schema.columns.items()
        }
        new_primary_keys = tuple(
            self._mapping.get(k, k) for k in schema.primary_keys
        )
        new_nullable = tuple(
            self._mapping.get(k, k) for k in schema.nullable
        )
        return DataSchema(
            columns=new_columns,
            primary_keys=new_primary_keys,
            nullable=new_nullable,
        )
