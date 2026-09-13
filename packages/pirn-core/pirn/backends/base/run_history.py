from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.backends.base.run_retention import RunRetention
from pirn.core.pirn_opaque_value import PirnOpaqueValue

if TYPE_CHECKING:
    from pirn.core.knot_lineage import KnotLineage
    from pirn.core.knot_source_record import KnotSourceRecord


class RunHistory(PirnOpaqueValue):
    """Interface: where run results and lineage records are persisted.

    Implementations inherit from this class and override all methods.

    Mixes in :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` (ADR
    "agents speaks core" WS3) for the same reason
    :class:`~pirn.backends.base.data_store.DataStore` does: a ``Knot`` that
    wants to query lineage directly (a session-chain reader, a lineage-based
    recall knot) must be able to declare ``RunHistory`` as a typed
    ``process()`` parameter, which requires a pydantic-core schema.
    """

    @property
    def retention(self) -> RunRetention:
        """Declare how much history this backend keeps.

        Defaults to durable and unbounded, which is right for a real store.  An
        ephemeral backend overrides this to declare its ceiling, so callers that
        would otherwise grow history without limit — ``LoopSubTapestry``, whose
        conversational flows record one child run per turn — can be recorded
        against a bounded window instead of being skipped outright.

        This exists so the engine never has to ask what *class* a store is.
        See PIR-765.
        """
        return RunRetention()

    async def record_run(self, result: Any) -> None:
        """Persist a completed run and its per-knot lineage records.

        Args:
            result: A ``RunResult`` containing run-level metadata and a list
                of ``KnotLineage`` records for every knot that executed.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement record_run()")

    async def get_run(self, run_id: str) -> Any:
        """Fetch a single run by its unique identifier.

        Args:
            run_id: UUID string assigned to the run at dispatch time.

        Returns:
            A ``RunResult`` instance, or ``None`` if the run is not found.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement get_run()")

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]:
        """Return all lineage records whose output matched ``output_hash``.

        Useful for tracing which knots produced a given artifact across all
        historical runs.

        Args:
            output_hash: Content hash of the output value to search for.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement query_lineage_by_output_hash()"
        )

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]:
        """Return all lineage records that consumed ``input_hash`` as an input.

        Useful for forward-tracing: given an artifact hash, find every knot
        that depended on it.

        Args:
            input_hash: Content hash of the input value to search for.

        Returns:
            List of ``KnotLineage`` records, possibly empty.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement query_lineage_by_input_hash()"
        )

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
        """Return all lineage records for a specific knot across all runs.

        Args:
            knot_id: Stable identifier of the knot whose history is requested.

        Returns:
            List of ``KnotLineage`` records ordered by insertion order,
            possibly empty.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement query_lineage_by_knot_id()"
        )

    async def query_latest_lineage_by_knot_id(self, knot_id: str) -> KnotLineage | None:
        """Return the most recently finished lineage record for ``knot_id``.

        The keyed-identity pattern (ADR "agents speaks core" WS3): a caller
        that treats a knot id as a keyed identity — one write per update,
        each its own lineage row — reads "the current value under this key"
        by finding the newest row rather than scanning every historical one.

        The default implementation is always correct but not necessarily
        efficient: it delegates to :meth:`query_lineage_by_knot_id` and takes
        the maximum by ``finished_at`` in Python, which is O(n) in how many
        times this knot id has ever run. A backend whose storage can answer
        "the latest row for this id" directly (an indexed column, not a JSON
        blob scan) should override this with that query instead.

        Args:
            knot_id: Stable identifier of the knot whose latest record is
                requested.

        Returns:
            The ``KnotLineage`` record with the greatest ``finished_at`` for
            ``knot_id``, or ``None`` if it has never run.
        """
        rows = await self.query_lineage_by_knot_id(knot_id)
        if not rows:
            return None
        return max(rows, key=lambda row: row.finished_at)

    async def query_runs_by_actor(self, actor: str) -> list[Any]:
        """Return all runs triggered by a specific actor.

        Args:
            actor: Human-readable actor string recorded at dispatch time
                (e.g. a username or service account name).

        Returns:
            List of ``RunResult`` objects, possibly empty.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement query_runs_by_actor()")

    async def children_of(self, run_id: str) -> list[Any]:
        """Return all runs whose parent_run_id matches run_id."""
        raise NotImplementedError(f"{type(self).__name__} must implement children_of()")

    async def record_knot_source(self, record: KnotSourceRecord) -> None:
        """Persist a knot source snapshot, ignoring duplicates.

        Implementations must be idempotent: inserting a record whose
        ``source_hash`` already exists in the store is a no-op.

        Args:
            record: The ``KnotSourceRecord`` to persist.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement record_knot_source()")

    async def get_knot_source(self, source_hash: str) -> KnotSourceRecord | None:
        """Fetch a knot source snapshot by its content hash.

        Args:
            source_hash: SHA-256 hex digest as stored in ``KnotLineage.source_hash``.

        Returns:
            A ``KnotSourceRecord``, or ``None`` if the hash is not found.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement get_knot_source()")
