# Local type stub for the part of ``pyarrow.lib`` pirn-data uses.
#
# pyarrow is a compiled (Cython) extension that ships no stubs, so pyright sees
# every name in it as Unknown. This stub declares the subset of the public API
# pirn_data calls (and that the typed stubs of duckdb / polars / datafusion
# reference), with signatures taken from pyarrow 25. Add a member here when
# pirn_data starts using it (``[tool.pyright].stubPath`` in pyproject.toml).

from collections.abc import Iterator, Mapping, Sequence
from typing import Any, overload

from pyarrow.compute import Expression


class DataType:
    id: int
    bit_width: int
    num_fields: int

    def equals(self, other: DataType | str, *, check_metadata: bool = False) -> bool: ...


class Field:
    name: str
    type: DataType
    nullable: bool


class Schema:
    names: list[str]
    types: list[DataType]

    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[Field]: ...
    def field(self, i: int | str) -> Field: ...
    def get_field_index(self, name: str) -> int: ...


class Array:
    type: DataType
    null_count: int

    def __len__(self) -> int: ...
    def to_pylist(self) -> list[Any]: ...


class ChunkedArray:
    type: DataType
    null_count: int
    num_chunks: int

    def __len__(self) -> int: ...
    def to_pylist(self) -> list[Any]: ...


class TableGroupBy:
    def aggregate(self, aggregations: Sequence[tuple[str, str]]) -> Table: ...


class Table:
    num_rows: int
    num_columns: int
    column_names: list[str]
    schema: Schema

    @classmethod
    def from_pylist(
        cls,
        mapping: Sequence[Mapping[str, Any]],
        schema: Schema | None = None,
        metadata: Mapping[str | bytes, str | bytes] | None = None,
    ) -> Table: ...
    def __len__(self) -> int: ...
    def column(self, i: int | str) -> ChunkedArray: ...
    def set_column(self, i: int, field_: str | Field, column: Array | ChunkedArray) -> Table: ...
    def append_column(self, field_: str | Field, column: Array | ChunkedArray) -> Table: ...
    def group_by(self, keys: str | Sequence[str], use_threads: bool = True) -> TableGroupBy: ...
    def rename_columns(self, names: Sequence[str] | Mapping[str, str]) -> Table: ...
    def filter(
        self,
        mask: Array | ChunkedArray | Expression,
        null_selection_behavior: str = "drop",
    ) -> Table: ...
    def join(
        self,
        right_table: Table,
        keys: str | Sequence[str],
        right_keys: str | Sequence[str] | None = None,
        join_type: str = "left outer",
        left_suffix: str | None = None,
        right_suffix: str | None = None,
        coalesce_keys: bool = True,
        use_threads: bool = True,
    ) -> Table: ...
    def take(self, indices: Array | ChunkedArray | Sequence[int]) -> Table: ...
    def to_pylist(self) -> list[dict[str, Any]]: ...


class RecordBatch:
    num_rows: int
    num_columns: int
    schema: Schema

    def to_pylist(self) -> list[dict[str, Any]]: ...


class RecordBatchReader:
    schema: Schema

    def read_all(self) -> Table: ...
    def __iter__(self) -> Iterator[RecordBatch]: ...


def int64() -> DataType: ...
def float64() -> DataType: ...
def string() -> DataType: ...
def bool_() -> DataType: ...
def field(
    name: str,
    type: DataType | None = None,
    nullable: bool | None = None,
    metadata: Mapping[str | bytes, str | bytes] | None = None,
) -> Field: ...
@overload
def array(obj: Sequence[Any] | range, type: DataType | None = None) -> Array: ...
@overload
def array(obj: Iterator[Any], type: DataType | None = None, size: int | None = None) -> Array: ...
def table(
    data: Mapping[str, Array | ChunkedArray | Sequence[Any]] | Sequence[Array | ChunkedArray],
    names: Sequence[str] | None = None,
    schema: Schema | None = None,
    metadata: Mapping[str | bytes, str | bytes] | None = None,
    nthreads: int | None = None,
) -> Table: ...
