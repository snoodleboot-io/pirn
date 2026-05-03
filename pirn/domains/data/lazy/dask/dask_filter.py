"""``DaskFilter`` — Tier-3 row predicate that extends the deferred Dask
graph with a boolean-mask filter.

The predicate is a callable that takes a ``dask.dataframe.DataFrame``
and returns a boolean ``dask.dataframe.Series``::

    DaskFilter(
        batch=upstream,
        predicate=lambda frame: frame.region == "EU",
        _config=KnotConfig(id="eu_only"),
    )

No partitions are computed here — the resulting frame is still lazy and
will be evaluated only when the terminal sink calls ``.compute()``.
"""

from __future__ import annotations

from typing import Any, Callable

import dask.dataframe as dd

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame


class DaskFilter(Knot):
    """Apply ``frame[predicate(frame)]`` to a deferred Dask DataFrame."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Callable[[dd.DataFrame], dd.Series],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not callable(predicate):
            raise TypeError(
                "DaskFilter: predicate must be a callable "
                "(frame) -> dask.dataframe.Series"
            )
        self._predicate = predicate
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def predicate(self) -> Callable[[dd.DataFrame], dd.Series]:
        return self._predicate

    async def process(self, batch: DaskDataFrame, **_: Any) -> DaskDataFrame:
        """Apply the callable boolean-mask predicate to the deferred Dask frame and return the filtered result.

        Args:
            batch: The upstream DaskDataFrame to filter.

        Returns:
            A new DaskDataFrame with the predicate applied to the deferred graph.
        """
        mask = self._predicate(batch.frame)
        return batch.with_frame(batch.frame[mask])
