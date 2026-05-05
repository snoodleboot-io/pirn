"""``Filter`` — keep only rows where the predicate returns truthy.

The predicate receives one row at a time (a ``Mapping[str, Any]``) and
returns a boolean-like value. Rows whose predicate result is falsy are
dropped; the rest pass through with the schema unchanged.

Algorithm:
    1. Validate that ``predicate`` is callable. Raise ``TypeError`` otherwise.
    2. Iterate over every row in the batch, invoking ``predicate(row)`` for
       each one.
    3. Keep rows whose predicate result is truthy; discard the rest.
    4. Return a new batch with the surviving rows and the original schema
       unchanged.

    ```text
    kept = [row for row in rows if predicate(row)]
    return batch.with_rows(kept)
    ```

References:
    [1] Python built-in ``filter()`` — equivalent single-iterable API (not
        used here because pirn batches are typed ``DataBatch`` objects, not
        bare iterables):
        https://docs.python.org/3/library/functions.html#filter
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class Filter(Knot):
    """Drop rows for which ``predicate(row)`` is falsy."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Knot | Callable[[Mapping[str, Any]], bool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, predicate=predicate, _config=_config, **kwargs)

    async def process(
        self,
        batch: DataBatch,
        predicate: Any,
        **_: Any,
    ) -> DataBatch:
        """Apply the callable predicate to each row and return a batch containing only truthy rows.

        Args:
            batch: The DataBatch to filter.
            predicate: A callable that accepts a row mapping and returns truthy/falsy.

        Returns:
            A new DataBatch containing only the rows for which the predicate returned truthy.
        """
        if not callable(predicate):
            raise TypeError("Filter: predicate must be callable")
        kept = tuple(row for row in batch.rows if predicate(row))
        return batch.with_rows(kept)
