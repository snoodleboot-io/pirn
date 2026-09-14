# Local type stub for the part of ``pyarrow.dataset`` pirn-data uses (see lib.pyi).

from collections.abc import Sequence

from pyarrow.compute import Expression
from pyarrow.lib import Schema, Table


class Dataset:
    schema: Schema

    def to_table(
        self,
        columns: Sequence[str] | None = None,
        filter: Expression | None = None,
    ) -> Table: ...


def dataset(
    source: str | Sequence[str],
    schema: Schema | None = None,
    format: str | None = None,
) -> Dataset: ...
