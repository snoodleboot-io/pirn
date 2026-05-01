"""``PolarsRename`` — Tier-2 column-rename knot dispatching to
:meth:`polars.DataFrame.rename`.
"""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsRename(Knot):
    """Apply an old → new column name mapping using Polars's native rename."""

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
                "PolarsRename: mapping must be a non-empty Mapping[old_name, new_name]"
            )
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                raise TypeError(
                    "PolarsRename: mapping keys and values must be non-empty strings"
                )
        self._mapping: dict[str, str] = dict(mapping)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def mapping(self) -> Mapping[str, str]:
        return dict(self._mapping)

    async def process(self, batch: PolarsDataBatch, **_: Any) -> PolarsDataBatch:
        # Polars rejects unknown columns; restrict to those present.
        applicable = {
            old: new for old, new in self._mapping.items()
            if old in batch.frame.columns
        }
        return batch.with_frame(batch.frame.rename(applicable))
