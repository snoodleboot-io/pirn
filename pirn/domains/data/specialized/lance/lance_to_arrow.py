"""``LanceToArrow`` — Tier-4 to Arrow bridge knot.

Materialises a :class:`LanceDataset` into a :class:`pyarrow.Table` so
downstream Tier-2 consumers can hop into Polars / Pandas / DuckDB via
their respective ``from_arrow`` constructors. Uses the dataset's native
``to_table()`` method so column-pruning and filter push-downs configured
upstream (when those land) still apply.

The output is annotated as :class:`Any` rather than :class:`pyarrow.Table`
because Pydantic's ``TypeAdapter`` cannot generate a schema for raw
PyArrow tables; the caller is expected to know that the returned object
is a ``pyarrow.Table``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specialized.lance.lance_dataset import LanceDataset


class LanceToArrow(Knot):
    """Convert a :class:`LanceDataset` into a :class:`pyarrow.Table`."""

    def __init__(
        self,
        *,
        dataset: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(dataset=dataset, _config=_config, **kwargs)

    async def process(self, dataset: LanceDataset, **_: Any) -> Any:
        """Materialise the LanceDataset to a PyArrow table and return it.

        Args:
            dataset: The upstream LanceDataset to materialise.

        Returns:
            A pyarrow.Table containing all rows from the Lance dataset.
        """
        return dataset.dataset.to_table()
