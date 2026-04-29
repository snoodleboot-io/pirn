from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING, Any

from pirn.backends.base.run_history import RunHistory

if TYPE_CHECKING:
    from pirn.core.lineage import KnotLineage


class InMemoryHistory(RunHistory):
    """In-memory RunHistory.

    Stores RunResult objects keyed by run_id, plus indexes of lineage
    records by output_hash, input_hash, and knot_id.
    """

    def __init__(self) -> None:
        self._runs: dict[str, Any] = {}
        self._lineage_by_output: dict[str, list[KnotLineage]] = {}
        self._lineage_by_input: dict[str, list[KnotLineage]] = {}
        self._lineage_by_knot: dict[str, list[KnotLineage]] = {}
        self._lock = Lock()

    async def record_run(self, result: Any) -> None:
        with self._lock:
            self._runs[result.run_id] = result
            for rec in result.lineage:
                self._lineage_by_knot.setdefault(rec.knot_id, []).append(rec)
                if rec.output_hash:
                    self._lineage_by_output.setdefault(rec.output_hash, []).append(rec)
                for input_hash in rec.parent_input_hashes.values():
                    self._lineage_by_input.setdefault(input_hash, []).append(rec)

    async def get_run(self, run_id: str) -> Any:
        with self._lock:
            return self._runs.get(run_id)

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        with self._lock:
            return list(self._lineage_by_output.get(output_hash, []))

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        with self._lock:
            return list(self._lineage_by_input.get(input_hash, []))

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        with self._lock:
            return list(self._lineage_by_knot.get(knot_id, []))
