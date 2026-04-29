from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pirn.core.lineage import KnotLineage


class RunHistory:
    """Interface: where run results and lineage records are persisted.

    Implementations inherit from this class and override all methods.
    """

    async def record_run(self, result: Any) -> None:
        raise NotImplementedError(f"{type(self).__name__} must implement record_run()")

    async def get_run(self, run_id: str) -> Any:
        raise NotImplementedError(f"{type(self).__name__} must implement get_run()")

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        raise NotImplementedError(
            f"{type(self).__name__} must implement query_lineage_by_output_hash()"
        )

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        raise NotImplementedError(
            f"{type(self).__name__} must implement query_lineage_by_input_hash()"
        )

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        raise NotImplementedError(
            f"{type(self).__name__} must implement query_lineage_by_knot_id()"
        )
