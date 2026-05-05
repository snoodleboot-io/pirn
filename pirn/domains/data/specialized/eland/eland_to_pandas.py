"""``ElandToPandas`` — Tier-4 to Tier-2 bridge knot.

Materialises an :class:`ElandDataFrame` into a real
:class:`pandas.DataFrame` via :func:`eland.eland_to_pandas`. This is the
point at which Elasticsearch is actually queried — every prior
``ElandFilter``-style knot is a push-down that compiles to ES DSL but
defers execution; calling ``eland_to_pandas`` runs the compiled query
and pulls rows back to the client.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame


class ElandToPandas(Knot):
    """Materialise an :class:`ElandDataFrame` as a :class:`PandasDataBatch`."""

    def __init__(
        self,
        *,
        frame: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(frame=frame, _config=_config, **kwargs)

    async def process(self, frame: ElandDataFrame, **_: Any) -> PandasDataBatch:
        """Execute the Elasticsearch query and materialise the result as a PandasDataBatch.

        Args:
            frame: The upstream ElandDataFrame to materialise.

        Returns:
            A PandasDataBatch containing the rows returned by Elasticsearch.
        """
        import eland as ed

        materialised: pd.DataFrame = ed.eland_to_pandas(frame.frame)
        return PandasDataBatch(
            frame=materialised,
            source_uri=frame.source_uri,
            fetched_at=frame.fetched_at,
        )
