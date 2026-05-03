"""``PandasRename`` — Tier-2 column-rename knot dispatching to
:meth:`pandas.DataFrame.rename`.
"""

from __future__ import annotations

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasRename(Knot):
    """Apply an old → new column name mapping using Pandas's native rename."""

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
                "PandasRename: mapping must be a non-empty Mapping[old_name, new_name]"
            )
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                raise TypeError(
                    "PandasRename: mapping keys and values must be non-empty strings"
                )
        self._mapping: dict[str, str] = dict(mapping)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def mapping(self) -> Mapping[str, str]:
        return dict(self._mapping)

    async def process(self, batch: PandasDataBatch, **_: Any) -> PandasDataBatch:
        """Rename columns in the batch according to the configured mapping and return the result.

        Args:
            batch: The PandasDataBatch whose columns are to be renamed.

        Returns:
            A new PandasDataBatch with the applicable columns renamed.
        """
        # Restrict to columns actually present so callers can declare a
        # superset mapping safely (mirrors PolarsRename behaviour).
        applicable = {
            old: new for old, new in self._mapping.items()
            if old in batch.frame.columns
        }
        return batch.with_frame(batch.frame.rename(columns=applicable))
