"""In-memory backend implementations.

The Phase 2 default for ``TapestryStore``, ``RunHistory``, and
``DataStore``.  Single-process; lost on exit.  Thread-safe via locks
because async tasks may share the loop and the engine concurrently
dispatches knots.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING, Any

from pirn.backends import TapestrySnapshot

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.core.lineage import KnotLineage


# ---------------------------------------------------------------- store


class InMemoryStore:
    """In-memory ``TapestryStore``.

    Implements the optional ``SubscribableStore`` protocol: callers can
    ``subscribe(callback)`` to receive the newly-registered ``Knot`` on
    every successful registration.  Used by the engine's mid-run
    extension mode.
    """

    def __init__(self) -> None:
        self._knots: dict[str, Knot] = {}
        self._lock = Lock()
        self._subscribers: dict[int, Callable[[Knot], None]] = {}
        self._next_token: int = 0

    def register(self, knot: Knot) -> None:
        with self._lock:
            existing = self._knots.get(knot.knot_id)
            if existing is not None and existing is not knot:
                raise ValueError(
                    f"knot id {knot.knot_id!r} already registered with a different instance"
                )
            is_new = existing is None
            self._knots[knot.knot_id] = knot
            subscribers = list(self._subscribers.values()) if is_new else []
        # Call subscribers outside the lock so a slow subscriber can't
        # block other registrations.
        for cb in subscribers:
            try:
                cb(knot)
            except Exception:
                # A broken subscriber must not break registration.
                pass

    def get(self, knot_id: str) -> Knot | None:
        with self._lock:
            return self._knots.get(knot_id)

    def all(self) -> list[Knot]:
        with self._lock:
            return list(self._knots.values())

    def snapshot(self) -> TapestrySnapshot:
        with self._lock:
            return TapestrySnapshot(knot_ids=list(self._knots.keys()))

    def subscribe(self, callback) -> object:
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._subscribers[token] = callback
        return token

    def unsubscribe(self, token: object) -> None:
        with self._lock:
            self._subscribers.pop(token, None)  # type: ignore[arg-type]


# -------------------------------------------------------------- history


class InMemoryHistory:
    """In-memory ``RunHistory``.

    Stores ``RunResult`` objects keyed by run_id, plus an index of lineage
    records by output_hash, by input_hash, and by knot_id.  All queries
    are linear scans backed by these indexes; for large histories use a
    real backend (DuckDB / Postgres) in Phase 3+.
    """

    def __init__(self) -> None:
        self._runs: dict[str, Any] = {}  # run_id -> RunResult
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


# ------------------------------------------------------------- data store


class InMemoryDataStore:
    """In-memory ``DataStore``.

    Holds intermediate values keyed by content hash.  Scrubbing is
    immediate and irreversible.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._lock = Lock()

    async def put(self, content_hash: str, value: Any) -> None:
        with self._lock:
            self._values[content_hash] = value

    async def get(self, content_hash: str) -> Any:
        with self._lock:
            if content_hash not in self._values:
                raise KeyError(content_hash)
            return self._values[content_hash]

    async def has(self, content_hash: str) -> bool:
        with self._lock:
            return content_hash in self._values

    async def scrub(self, content_hash: str) -> None:
        with self._lock:
            self._values.pop(content_hash, None)
