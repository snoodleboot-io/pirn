"""``PolarsRename`` — Tier-2 column-rename knot dispatching to
:meth:`polars.DataFrame.rename`.

Algorithm:
    1. Validate ``mapping`` as a non-empty Mapping with non-empty string
       keys and values.
    2. Restrict ``mapping`` to entries whose old name exists in the frame
       (Polars rejects unknown columns; filtering upfront lets callers
       declare a superset mapping safely).
    3. Call ``frame.rename(applicable)`` and return the result wrapped in
       a new :class:`PolarsDataBatch`.

    ```text
    applicable = {old: new for old, new in mapping.items()
                  if old in frame.columns}
    return batch.with_frame(frame.rename(applicable))
    ```

References:
    [1] Polars — DataFrame.rename:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.rename.html
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsRename(Knot):
    """Apply an old → new column name mapping using Polars's native rename."""

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
        batch: PolarsDataBatch,
        mapping: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Rename columns in the batch according to the configured mapping and return the result.

        Args:
            batch: The upstream PolarsDataBatch whose columns will be renamed.
            mapping: Mapping of old column name to new column name.

        Returns:
            A new PolarsDataBatch with the applicable columns renamed.
        """
        if not isinstance(mapping, Mapping) or not mapping:
            raise TypeError("PolarsRename: mapping must be a non-empty Mapping[old_name, new_name]")
        for old, new in mapping.items():
            if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
                raise TypeError("PolarsRename: mapping keys and values must be non-empty strings")
        # Polars rejects unknown columns; restrict to those present.
        applicable = {old: new for old, new in mapping.items() if old in batch.frame.columns}
        return batch.with_frame(batch.frame.rename(applicable))
