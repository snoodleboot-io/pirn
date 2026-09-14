# Local type stub for the part of ``pyarrow.compute`` pirn-data uses (see lib.pyi).

from typing import overload

from pyarrow.lib import Array, ChunkedArray, DataType


class Expression:
    def __and__(self, other: Expression) -> Expression: ...
    def __or__(self, other: Expression) -> Expression: ...
    def __invert__(self) -> Expression: ...


@overload
def cast(
    arr: ChunkedArray,
    target_type: DataType | str | None = None,
    safe: bool | None = None,
) -> ChunkedArray: ...
@overload
def cast(
    arr: Array,
    target_type: DataType | str | None = None,
    safe: bool | None = None,
) -> Array: ...
@overload
def take(data: ChunkedArray, indices: Array | ChunkedArray) -> ChunkedArray: ...
@overload
def take(data: Array, indices: Array | ChunkedArray) -> Array: ...
def sort_indices(input: Array | ChunkedArray, /) -> Array: ...
