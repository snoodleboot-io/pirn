from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING, Any

from pirn.backends.base.run_history import RunHistory

if TYPE_CHECKING:
    from pirn.core.knot_source import KnotSourceRecord
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
        self._runs_by_actor: dict[str, list[Any]] = {}
        self._runs_by_parent: dict[str, list[Any]] = {}
        self._knot_sources: dict[str, KnotSourceRecord] = {}
        self._lock = Lock()

    async def record_run(self, result: Any) -> None:
        """Persist a run result and index its lineage records.

        Args:
            result: A ``RunResult`` instance to persist.
        """
        with self._lock:
            self._runs[result.run_id] = result
            if result.actor is not None:
                self._runs_by_actor.setdefault(result.actor, []).append(result)
            if result.parent_run_id is not None:
                self._runs_by_parent.setdefault(result.parent_run_id, []).append(result)
            for rec in result.lineage:
                self._lineage_by_knot.setdefault(rec.knot_id, []).append(rec)
                if rec.output_hash:
                    self._lineage_by_output.setdefault(rec.output_hash, []).append(rec)
                for input_hash in rec.parent_input_hashes.values():
                    self._lineage_by_input.setdefault(input_hash, []).append(rec)

    async def get_run(self, run_id: str) -> Any:
        """Fetch a single run by id.

        Args:
            run_id: UUID of the run to retrieve.

        Returns:
            A ``RunResult`` instance, or ``None`` if not found.
        """
        with self._lock:
            return self._runs.get(run_id)

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        """Return all lineage records whose output matched ``output_hash``.

        Args:
            output_hash: Content hash of the output to search for.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        with self._lock:
            return list(self._lineage_by_output.get(output_hash, []))

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        """Return all lineage records that consumed ``input_hash`` as an input.

        Args:
            input_hash: Content hash of the input to search for.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        with self._lock:
            return list(self._lineage_by_input.get(input_hash, []))

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        """Return all lineage records for a specific knot across all runs.

        Args:
            knot_id: Identifier of the knot whose history is requested.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        with self._lock:
            return list(self._lineage_by_knot.get(knot_id, []))

    async def query_runs_by_actor(self, actor: str) -> list[Any]:
        """Return all runs triggered by ``actor``.

        Args:
            actor: Actor string to filter by.

        Returns:
            List of ``RunResult`` objects, possibly empty.
        """
        with self._lock:
            return list(self._runs_by_actor.get(actor, []))

    async def children_of(self, run_id: str) -> list[Any]:
        """Return all runs whose ``parent_run_id`` matches ``run_id``.

        Args:
            run_id: UUID of the parent run.

        Returns:
            List of ``RunResult`` objects for all child runs, possibly empty.
        """
        with self._lock:
            return list(self._runs_by_parent.get(run_id, []))

    async def record_knot_source(self, record: KnotSourceRecord) -> None:
        """Persist a knot source snapshot; no-op if the hash already exists.

        Args:
            record: The ``KnotSourceRecord`` to persist.
        """
        with self._lock:
            self._knot_sources.setdefault(record.source_hash, record)

    async def get_knot_source(self, source_hash: str) -> KnotSourceRecord | None:
        """Fetch a knot source snapshot by content hash.

        Args:
            source_hash: SHA-256 hex digest as stored in ``KnotLineage.source_hash``.

        Returns:
            A ``KnotSourceRecord``, or ``None`` if not found.
        """
        with self._lock:
            return self._knot_sources.get(source_hash)
