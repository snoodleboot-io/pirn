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

Algorithm:
    1. Validate that ``predicate`` is callable.
    2. Invoke ``predicate(frame)`` to obtain a boolean ``dask.dataframe.Series`` mask.
    3. Apply ``frame[mask]`` to extend the deferred computation graph.
    4. Return a new ``DaskDataFrame`` wrapping the filtered, still-deferred graph.

    ```text
    mask = predicate(frame)
    return DaskDataFrame(frame[mask])
    ```

References:
    [1] Dask DataFrame — boolean indexing / filtering:
        https://docs.dask.org/en/stable/dataframe-indexing.html
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import dask.dataframe as dd
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.lazy.dask.dask_dataframe import DaskDataFrame


class DaskFilter(Knot):
    """Apply ``frame[predicate(frame)]`` to a deferred Dask DataFrame."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Knot | Callable[[dd.DataFrame], dd.Series],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, predicate=predicate, _config=_config, **kwargs)

    async def process(self, batch: DaskDataFrame, predicate: Any, **_: Any) -> DaskDataFrame:
        """Apply the callable boolean-mask predicate to the deferred Dask frame.

        Args:
            batch: The upstream DaskDataFrame to filter.
            predicate: A callable (frame) -> dask.dataframe.Series.

        Returns:
            A new DaskDataFrame with the predicate applied to the deferred graph.
        """
        if not callable(predicate):
            raise TypeError(
                "DaskFilter: predicate must be a callable (frame) -> dask.dataframe.Series"
            )
        mask = predicate(batch.frame)
        return batch.with_frame(batch.frame[mask])
