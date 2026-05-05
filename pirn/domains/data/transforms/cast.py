"""``Cast`` — coerce values per column to a target type.

The target type's call signature is used: ``Cast(casts={"id": int})``
applies ``int(value)``. The batch's :class:`DataSchema` is updated so
downstream type checks see the post-cast types.

Failure modes:
- A value that the target type cannot construct from raises
  ``ValueError`` (or whatever the target type raises). The pipeline
  fails loudly — silent coercion of malformed data is the wrong default
  for analytics workloads.
- ``None`` values pass through untouched (consistent with the schema
  model, where ``nullable`` is a separate concern).

Algorithm:
    1. Validate ``casts``: must be a non-empty ``Mapping[str, type]`` with
       non-empty string keys and ``type`` values.
    2. For each row in the batch, iterate over every column. If the column
       appears in ``casts`` and its value is not ``None``, apply
       ``target_type(value)``. If the value is already an instance of the
       target type, return it as-is to avoid unnecessary re-construction.
    3. Collect the rewritten rows and update the :class:`DataSchema` so
       downstream Knots see the new type annotations.

    ```text
    for row in rows:
        for col, value in row:
            if col in casts and value is not None:
                out[col] = target_type(value)   # raises on bad data
            else:
                out[col] = value
    new_schema = schema.with_columns(casts)
    ```

References:
    [1] Python built-in type constructors (``int``, ``float``, ``str``, …) —
        the casting mechanism is delegated entirely to the caller-supplied type:
        https://docs.python.org/3/library/functions.html#built-in-functions
    [2] Apache Arrow ``cast`` — alternative push-down approach for
        Tier-3+ pipelines (chosen dict-based approach here for Tier-1
        portability across all engines):
        https://arrow.apache.org/docs/python/api/datatypes.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class Cast(Knot):
    """Coerce values per column to caller-specified target types."""

    def __init__(
        self,
        *,
        batch: Knot,
        casts: Knot | Mapping[str, type],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, casts=casts, _config=_config, **kwargs)

    async def process(
        self,
        batch: DataBatch,
        casts: Any,
        **_: Any,
    ) -> DataBatch:
        """Coerce each configured column to its target type and return the updated batch.

        Args:
            batch: The DataBatch whose column values will be coerced.
            casts: Mapping of column name to target type.

        Returns:
            A new DataBatch with cast column values and an updated schema reflecting the new types.
        """
        if not isinstance(casts, Mapping) or not casts:
            raise TypeError(
                "Cast: casts must be a non-empty Mapping[column, type]"
            )
        for column, target in casts.items():
            if not isinstance(column, str) or not column:
                raise TypeError("Cast: casts keys must be non-empty strings")
            if not isinstance(target, type):
                raise TypeError(
                    f"Cast: casts[{column!r}] must be a type, "
                    f"got {type(target).__name__}"
                )
        casts_dict: dict[str, type] = dict(casts)
        new_rows = tuple(self._cast_row(row, casts_dict) for row in batch.rows)
        new_schema = batch.schema.with_columns(casts_dict)
        return batch.with_rows(new_rows).with_schema(new_schema)

    @staticmethod
    def _cast_row(
        row: Mapping[str, Any],
        casts: dict[str, type],
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in row.items():
            if key in casts and value is not None:
                out[key] = Cast._coerce(key, value, casts[key])
            else:
                out[key] = value
        return out

    @staticmethod
    def _coerce(column: str, value: Any, target: type) -> Any:
        if isinstance(value, target):
            return value
        try:
            return target(value)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Cast: column {column!r} could not coerce value to "
                f"{target.__name__}"
            ) from exc
