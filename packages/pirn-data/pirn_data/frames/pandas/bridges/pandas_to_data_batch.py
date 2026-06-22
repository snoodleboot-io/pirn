"""``PandasToDataBatch`` — bridge knot from Tier-2 :class:`PandasDataBatch`
back to Tier-1 :class:`DataBatch`.

Materialises every row as a dict — only do this at the boundary where
downstream knots actually need the dict-based contract (a Tier-1 sink, a
small validator, or a debug step). For larger frames, prefer routing the
:class:`PandasDataBatch` directly into a Tier-2 sink.

Algorithm:
    1. Receive a :class:`PandasDataBatch` whose ``frame`` is a
       ``pd.DataFrame``.
    2. Call ``frame.to_dict(orient="records")`` to produce a list of
       ``dict[str, Any]`` — one dict per row.
    3. Convert the list to a ``tuple`` to satisfy the immutable
       ``DataBatch.rows`` contract.
    4. Construct a Tier-1 :class:`DataBatch` with the materialised rows,
       copying ``source_uri`` and ``fetched_at`` from the incoming batch.
    5. Return the :class:`DataBatch` to the downstream knot.

References:
    - pandas ``DataFrame.to_dict``:
      https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_dict.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.data_batch import DataBatch
from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch


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
