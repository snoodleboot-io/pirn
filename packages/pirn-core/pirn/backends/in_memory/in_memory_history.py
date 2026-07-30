from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING, Any

from pirn.backends.base.run_history import RunHistory
from pirn.backends.base.run_retention import RunRetention

if TYPE_CHECKING:
    from pirn.core.knot_source import KnotSourceRecord
    from pirn.core.lineage import KnotLineage


class InMemoryHistory(RunHistory):
    """In-memory RunHistory.

    Stores RunResult objects keyed by run_id, plus indexes of lineage
    records by output_hash, input_hash, and knot_id.

    Being ephemeral, it keeps a **bounded** window: past ``max_runs`` the oldest
    run is evicted along with its lineage index entries.  The bound is declared
    via :attr:`retention` rather than inferred from the class, so a caller that
    would otherwise grow history without limit can record against it safely
    instead of being skipped.  ``LoopSubTapestry`` is the case that needs this —
    an open-ended conversational loop records one child run per turn.  See
    PIR-765.

    The default ceiling is high enough that ordinary pipelines never reach it;
    it is a guard against unbounded growth, not a working-set limit.
    """

    #: Default retained-run ceiling.  Sized so normal use never evicts.
    DEFAULT_MAX_RUNS: int = 10_000

    def __init__(self, *, max_runs: int | None = None) -> None:
        """Initialise the store.

        Args:
            max_runs: Retained-run ceiling.  Defaults to
                :attr:`DEFAULT_MAX_RUNS`.  Pass an explicit value to tighten it
                for a long-running session.
        """
        if max_runs is not None and max_runs <= 0:
            raise ValueError(f"InMemoryHistory: max_runs must be positive, got {max_runs!r}")
        self._max_runs: int = InMemoryHistory.DEFAULT_MAX_RUNS if max_runs is None else max_runs
        self._runs: dict[str, Any] = {}
        self._lineage_by_output: dict[str, list[KnotLineage]] = {}
        self._lineage_by_input: dict[str, list[KnotLineage]] = {}
        self._lineage_by_knot: dict[str, list[KnotLineage]] = {}
        self._runs_by_actor: dict[str, list[Any]] = {}
        self._runs_by_parent: dict[str, list[Any]] = {}
        self._knot_sources: dict[str, KnotSourceRecord] = {}
        self._lock = Lock()

    @property
    def retention(self) -> RunRetention:
        """Declare the bounded window this store keeps."""
        return RunRetention(max_runs=self._max_runs)

    async def record_run(self, result: Any) -> None:
        """Persist a run result and index its lineage records.

        Evicts the oldest run once the retained count exceeds ``max_runs``.

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
            self._evict_to_bound()

    def _evict_to_bound(self) -> None:
        """Drop oldest runs until the retained count is within ``max_runs``.

        Caller must hold ``self._lock``.  Every index entry the evicted run
        contributed goes with it — bounding ``_runs`` alone would leave lineage
        growing without limit, which is the thing this exists to prevent.
        """
        while len(self._runs) > self._max_runs:
            # dicts preserve insertion order, so the first key is the oldest run.
            oldest_id = next(iter(self._runs))
            self._purge_indexes(self._runs.pop(oldest_id))

    def _purge_indexes(self, evicted: Any) -> None:
        """Remove every index entry contributed by ``evicted``.

        Records are matched by identity, not equality: two runs can produce
        lineage records that compare equal, and dropping a live one would be
        worse than keeping a dead one.
        """
        if evicted.actor is not None:
            self._drop_from(self._runs_by_actor, evicted.actor, evicted)
        if evicted.parent_run_id is not None:
            self._drop_from(self._runs_by_parent, evicted.parent_run_id, evicted)
        for rec in evicted.lineage:
            self._drop_from(self._lineage_by_knot, rec.knot_id, rec)
            if rec.output_hash:
                self._drop_from(self._lineage_by_output, rec.output_hash, rec)
            for input_hash in rec.parent_input_hashes.values():
                self._drop_from(self._lineage_by_input, input_hash, rec)

    @staticmethod
    def _drop_from(index: dict[str, list[Any]], key: str, item: Any) -> None:
        """Remove ``item`` from ``index[key]`` by identity, pruning empty keys."""
        bucket = index.get(key)
        if bucket is None:
            return
        remaining = [entry for entry in bucket if entry is not item]
        if remaining:
            index[key] = remaining
        else:
            del index[key]

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
