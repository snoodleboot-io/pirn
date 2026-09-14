# Local type stub for the part of ``dask.dataframe`` pirn-data calls.
#
# dask's inline annotations leave the collection methods pirn_data uses
# (``groupby().agg``, ``merge``, ``compute`` ...) partially untyped. This stub
# declares exactly that surface with precise signatures taken from dask 2026.7.
# Add a member here when pirn_data starts using it (``[tool.pyright].stubPath``).

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pandas


class Index:
    def __iter__(self) -> Iterator[Any]: ...
    def tolist(self) -> list[Any]: ...


class Series: ...


class DataFrameGroupBy:
    def agg(self, arg: Mapping[str, Any]) -> DataFrame: ...


class DataFrame:
    columns: Index
    npartitions: int

    def __getitem__(self, key: Series) -> DataFrame: ...
    def groupby(self, by: str | Sequence[str]) -> DataFrameGroupBy: ...
    def reset_index(self, drop: bool = False) -> DataFrame: ...
    def merge(
        self,
        right: DataFrame,
        how: str = "inner",
        on: str | Sequence[str] | None = None,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
    ) -> DataFrame: ...
    def compute(self) -> pandas.DataFrame: ...
