"""``Rename`` — rename columns in a :class:`DataBatch` according to a
``Mapping[old_name, new_name]``.

Columns absent from the mapping pass through unchanged. The batch's
:class:`DataSchema` is updated so downstream consumers see the new names
in ``columns``, ``primary_keys``, and ``nullable``.

Algorithm:
    1. Validate ``mapping``: must be a non-empty ``Mapping[str, str]`` with
       non-empty string keys and values.
    2. For each row, build a new dict substituting the mapped column names.
       Columns not present in the mapping keep their original names.
    3. Rebuild the :class:`DataSchema`:

       a. ``columns``: apply the mapping to each column name.
       b. ``primary_keys``: apply the mapping to each key name.
       c. ``nullable``: apply the mapping to each nullable column name.

    4. Return a new batch with the renamed rows and updated schema.

    ```text
    for row in rows:
        emit {mapping.get(col, col): value for col, value in row}
    new_schema = schema with all names remapped
    ```

References:
    [1] Python ``dict`` — ``get(key, default)`` idiom used for identity
        pass-through of unmapped columns:
        https://docs.python.org/3/library/stdtypes.html#dict.get
    [2] dbt ``rename`` macro pattern — equivalent SQL-level column aliasing:
        https://docs.getdbt.com/docs/build/jinja-macros
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
        mapping: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, mapping=mapping, _config=_config, **kwargs)

    async def process(
        self,
        batch: DataBatch,
        mapping: Any,
        **_: Any,
    ) -> DataBatch:
        """Rename columns in each row according to the mapping and return the updated batch.

        Args:
            batch: The DataBatch whose column names will be remapped.
            mapping: Mapping of old column name to new column name.

        Returns:
            A new DataBatch with columns renamed and the schema updated to reflect the new names.
        """
        if not isinstance(mapping, Mapping) or not mapping:
            raise TypeError("Rename: mapping must be a non-empty Mapping[old_name, new_name]")
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str):
                raise TypeError("Rename: mapping keys and values must be strings")
            if not old or not new:
                raise ValueError("Rename: mapping keys and values must be non-empty")
        mapping_dict: dict[str, str] = dict(mapping)
        new_rows = tuple(self._rename_row(row, mapping_dict) for row in batch.rows)
        new_schema = self._rename_schema(batch.schema, mapping_dict)
        return batch.with_rows(new_rows).with_schema(new_schema)

    @staticmethod
    def _rename_row(
        row: Mapping[str, Any],
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        return {mapping.get(k, k): v for k, v in row.items()}

    @staticmethod
    def _rename_schema(schema: DataSchema, mapping: dict[str, str]) -> DataSchema:
        new_columns = {
            mapping.get(name, name): expected_type for name, expected_type in schema.columns.items()
        }
        new_primary_keys = tuple(mapping.get(k, k) for k in schema.primary_keys)
        new_nullable = tuple(mapping.get(k, k) for k in schema.nullable)
        return DataSchema(
            columns=new_columns,
            primary_keys=new_primary_keys,
            nullable=new_nullable,
        )
