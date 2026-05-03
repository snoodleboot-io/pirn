"""``PandasFilter`` — Tier-2 row predicate using a callable that returns a
boolean mask.

Pandas does not have a native expression syntax like Polars. Instead,
this knot expects a callable ``predicate(df) -> pandas.Series[bool]``
(or any boolean-mask-like indexer accepted by ``df[mask]``). The
callable is applied once to the whole frame, so vectorised mask
construction is preferred (e.g.
``lambda df: df["region"] == "EU"``).

Example::

    PandasFilter(
        batch=upstream,
        predicate=lambda df: df["region"] == "EU",
        _config=KnotConfig(id="eu_only"),
    )
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasFilter(Knot):
    """Apply a callable boolean-mask predicate to a :class:`PandasDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Callable[[pd.DataFrame], "pd.Series[bool]"],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not callable(predicate):
            raise TypeError(
                "PandasFilter: predicate must be a callable "
                "(df) -> pandas.Series[bool]; for row-by-row Python callables "
                "use the Tier-1 pirn.domains.data.transforms.filter.Filter knot instead"
            )
        self._predicate = predicate
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def predicate(self) -> Callable[[pd.DataFrame], "pd.Series[bool]"]:
        return self._predicate

    async def process(self, batch: PandasDataBatch, **_: Any) -> PandasDataBatch:
        """Apply the callable predicate to produce a boolean mask and return the filtered batch.

        Args:
            batch: The PandasDataBatch to filter.

        Returns:
            A new PandasDataBatch containing only the rows for which the predicate returns True.
        """
        mask = self._predicate(batch.frame)
        return batch.with_frame(batch.frame[mask].reset_index(drop=True))
