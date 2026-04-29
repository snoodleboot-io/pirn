"""Backend protocols.

Three orthogonal concerns, three protocols:

* ``TapestryStore`` — where the tapestry's *definition* lives (the set of
  knots and how they're wired).  Phase 2: in-memory only.  Phase 3+:
  SQLite, Postgres, ValKey.
* ``RunHistory`` — where lineage records and ``RunResult`` summaries are
  persisted.  Phase 2: in-memory only.  Phase 3+: DuckDB, Postgres.
* ``DataStore`` — where intermediate values live, keyed by content hash.
  Phase 2: in-memory only.  Phase 3+: local disk, S3, ValKey.

Splitting them lets each backend be picked for its strength: Postgres for
both store and history, SQLite for store + DuckDB for history, etc.
"""

from __future__ import annotations

import base64
import os
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.core.lineage import KnotLineage


class TapestrySnapshot(BaseModel):
    """An immutable view of a tapestry at a moment in time.

    Returned by ``TapestryStore.snapshot()``.  The engine takes a snapshot
    when planning a run so concurrent mutations to the store don't
    disturb the in-flight run.

    Phase 2: this is essentially the list of knot ids; the engine reads
    knots from the store directly.  Phase 3+ may carry richer state.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    knot_ids: list[str] = Field(default_factory=list)


@runtime_checkable
class TapestryStore(Protocol):
    """Where the tapestry's canonical definition lives."""

    def register(self, knot: Knot) -> None:
        """Add a knot.  Idempotent for the same instance; conflicts on id."""

    def get(self, knot_id: str) -> Knot | None: ...

    def all(self) -> list[Knot]: ...

    def snapshot(self) -> TapestrySnapshot: ...


@runtime_checkable
class RunHistory(Protocol):
    """Where run results and lineage records are persisted."""

    async def record_run(self, result: Any) -> None: ...

    async def get_run(self, run_id: str) -> Any: ...

    async def query_lineage_by_output_hash(self, output_hash: str) -> list[KnotLineage]: ...

    async def query_lineage_by_input_hash(self, input_hash: str) -> list[KnotLineage]: ...

    async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]: ...


@runtime_checkable
class DataStore(Protocol):
    """Where intermediate values live, keyed by content hash.

    Lineage references values by hash; the data store holds them by hash.
    Scrubbing values from the data store does not affect lineage.
    """

    async def put(self, content_hash: str, value: Any) -> None: ...

    async def get(self, content_hash: str) -> Any: ...

    async def has(self, content_hash: str) -> bool: ...

    async def scrub(self, content_hash: str) -> None:
        """Remove a value.  Lineage referencing it remains intact."""


def signing_key_from_env(var: str = "PIRN_SIGNING_KEY") -> bytes:
    """Read a base64-encoded signing key from an environment variable.

    Raises ``ValueError`` with a clear message if the variable is unset
    or empty.  The key is decoded from standard base64 before use.

    Example::

        import secrets, base64
        key_b64 = base64.b64encode(secrets.token_bytes(32)).decode()
        # Set PIRN_SIGNING_KEY=<key_b64> in your environment, then:
        store = LocalDiskDataStore("/data", signing_key=signing_key_from_env())
    """
    raw = os.environ.get(var)
    if not raw:
        raise ValueError(
            f"Environment variable {var!r} is not set or empty. "
            "Set it to a base64-encoded signing key before constructing a signed DataStore."
        )
    return base64.b64decode(raw)
