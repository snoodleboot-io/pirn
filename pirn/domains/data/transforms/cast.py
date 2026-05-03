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
"""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class Cast(Knot):
    """Coerce values per column to caller-specified target types."""

    def __init__(
        self,
        *,
        batch: Knot,
        casts: Mapping[str, type],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._casts: dict[str, type] = dict(casts)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def casts(self) -> Mapping[str, type]:
        return dict(self._casts)

    async def process(self, batch: DataBatch, **_: Any) -> DataBatch:
        """Coerce each configured column to its target type and return the updated batch.

        Args:
            batch: The DataBatch whose column values will be coerced.

        Returns:
            A new DataBatch with cast column values and an updated schema reflecting the new types.
        """
        new_rows = tuple(self._cast_row(row) for row in batch.rows)
        new_schema = batch.schema.with_columns(self._casts)
        return batch.with_rows(new_rows).with_schema(new_schema)

    def _cast_row(
        self, row: Mapping[str, Any]
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in row.items():
            if key in self._casts and value is not None:
                out[key] = self._coerce(key, value, self._casts[key])
            else:
                out[key] = value
        return out

    def _coerce(self, column: str, value: Any, target: type) -> Any:
        if isinstance(value, target):
            return value
        try:
            return target(value)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Cast: column {column!r} could not coerce value to "
                f"{target.__name__}"
            ) from exc
