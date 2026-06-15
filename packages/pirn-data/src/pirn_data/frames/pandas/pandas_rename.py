"""``PandasRename`` — Tier-2 column-rename knot dispatching to
:meth:`pandas.DataFrame.rename`.

Algorithm:
    1. Validate ``mapping`` as a non-empty Mapping with non-empty string
       keys and values.
    2. Restrict ``mapping`` to entries whose old name exists in the frame
       (unknown columns are silently ignored so a superset mapping is safe).
    3. Call ``frame.rename(columns=applicable)`` and return the result
       wrapped in a new :class:`PandasDataBatch`.

    ```text
    applicable = {old: new for old, new in mapping.items()
                  if old in frame.columns}
    return batch.with_frame(frame.rename(columns=applicable))
    ```

References:
    [1] pandas — DataFrame.rename:
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rename.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasRename(Knot):
    """Apply an old → new column name mapping using Pandas's native rename."""

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
        batch: PandasDataBatch,
        mapping: Any,
        **_: Any,
    ) -> PandasDataBatch:
        """Rename columns in the batch according to the configured mapping and return the result.

        Args:
            batch: The PandasDataBatch whose columns are to be renamed.
            mapping: Mapping of old column name to new column name.

        Returns:
            A new PandasDataBatch with the applicable columns renamed.
        """
        if not isinstance(mapping, Mapping) or not mapping:
            raise TypeError("PandasRename: mapping must be a non-empty Mapping[old_name, new_name]")
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                raise TypeError("PandasRename: mapping keys and values must be non-empty strings")
        # Restrict to columns actually present so callers can declare a
        # superset mapping safely (mirrors PolarsRename behaviour).
        applicable = {old: new for old, new in mapping.items() if old in batch.frame.columns}
        return batch.with_frame(batch.frame.rename(columns=applicable))
