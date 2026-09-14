# Local type stub for the part of ``ibis`` (ibis-framework) pirn-data calls.
#
# ibis ships no stubs or py.typed marker. This stub declares the deferred-table
# surface pirn_data uses, with signatures taken from ibis-framework 12. Add a
# member here when pirn_data starts using it (``[tool.pyright].stubPath``).

from collections.abc import Sequence


class Expr: ...


class Schema: ...


class GroupedTable:
    def aggregate(self, *metrics: Expr) -> Table: ...


class Table(Expr):
    columns: tuple[str, ...]

    def schema(self) -> Schema: ...
    def count(self) -> Expr: ...
    def filter(self, *predicates: Expr) -> Table: ...
    def mutate(self, *exprs: Expr) -> Table: ...
    def group_by(self, *by: str | Sequence[str]) -> GroupedTable: ...
    def cross_join(self, right: Table, *rest: Table) -> Table: ...
    def join(
        self,
        right: Table,
        predicates: str | Sequence[str] | Expr | Sequence[Expr] = (),
        how: str = "inner",
    ) -> Table: ...

