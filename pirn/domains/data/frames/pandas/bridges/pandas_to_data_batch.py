"""``PandasToDataBatch`` — bridge knot from Tier-2 :class:`PandasDataBatch`
back to Tier-1 :class:`DataBatch`.

Materialises every row as a dict — only do this at the boundary where
downstream knots actually need the dict-based contract (a Tier-1 sink, a
small validator, or a debug step). For larger frames, prefer routing the
:class:`PandasDataBatch` directly into a Tier-2 sink.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasToDataBatch(Knot):
    """Materialise a :class:`PandasDataBatch` back into a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: PandasDataBatch, **_: Any) -> DataBatch:
        """Materialise the Pandas DataFrame to row dicts and return a Tier-1 DataBatch.

        Args:
            batch: The PandasDataBatch whose DataFrame is materialised to row dicts.

        Returns:
            A Tier-1 DataBatch with materialised rows, source_uri, and fetched_at preserved.
        """
        rows = tuple(batch.frame.to_dict(orient="records"))
        return DataBatch(
            rows=rows,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
