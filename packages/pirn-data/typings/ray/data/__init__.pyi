# Local type stub for the part of ``ray.data`` pirn-data calls.
#
# ray's inline annotations leave the Dataset methods pirn_data uses (``filter``,
# ``map_batches``, ``materialize`` ...) partially untyped. This stub declares
# exactly that surface with precise signatures taken from ray 2.58. Add a member
# here when pirn_data starts using it (``[tool.pyright].stubPath``).

from collections.abc import Callable
from typing import Any

import pandas


class GroupedData:
    def aggregate(self, *aggs: Any) -> Dataset: ...


class Dataset:
    def filter(self, fn: Callable[[dict[str, Any]], bool]) -> Dataset: ...
    def map_batches(
        self,
        fn: Callable[[Any], Any],
        *,
        batch_format: str | None = "default",
        batch_size: int | None = None,
    ) -> Dataset: ...
    def groupby(self, key: str | list[str]) -> GroupedData: ...
    def materialize(self) -> MaterializedDataset: ...
    def to_pandas(self) -> pandas.DataFrame: ...
    def count(self) -> int: ...
    def num_blocks(self) -> int: ...


class MaterializedDataset(Dataset): ...
