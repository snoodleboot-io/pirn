"""``Filter`` — keep only rows where the predicate returns truthy.

The predicate receives one row at a time (a ``Mapping[str, Any]``) and
returns a boolean-like value. Rows whose predicate result is falsy are
dropped; the rest pass through with the schema unchanged.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class Filter(Knot):
    """Drop rows for which ``predicate(row)`` is falsy."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Callable[[Mapping[str, Any]], bool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not callable(predicate):
            raise TypeError("Filter: predicate must be callable")
        self._predicate = predicate
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def predicate(self) -> Callable[[Mapping[str, Any]], bool]:
        return self._predicate

    async def process(self, batch: DataBatch, **_: Any) -> DataBatch:
        """Apply the callable predicate to each row and return a batch containing only truthy rows.

        Args:
            batch: The DataBatch to filter.

        Returns:
            A new DataBatch containing only the rows for which the predicate returned truthy.
        """
        kept = tuple(row for row in batch.rows if self._predicate(row))
        return batch.with_rows(kept)
