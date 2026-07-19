"""``PgvectorMemoryStore`` — a pgvector-backed :class:`VectorMemoryStore`.

Persists vectors in a Postgres table using the `pgvector` extension, driven by
the async `asyncpg` driver behind the ``[pgvector]`` extra. A connection pool is
built once and reused (the pooling lever); upserts are sent in batches via
``executemany``; metadata filters map to a jsonb-containment predicate and
nearest-neighbour ranking is done server-side with pgvector's cosine-distance
operator (``<=>``).

The driver import is lazy so importing this module stays backend-free. The pool
is an injectable seam, so mirrored tests drive the adapter against a stub
asyncpg double while the shared conformance suite runs against a real database
behind the ``needs_pgvector`` marker.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from pirn_agents._require import _require
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.vector_stores.vector_match import VectorMatch
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from pirn_agents.vector_stores.vector_record import VectorRecord


class PgvectorMemoryStore(VectorMemoryStore):
    """A Postgres/pgvector :class:`VectorMemoryStore` with pooled async I/O."""

    def __init__(
        self,
        *,
        dsn: str,
        table: str = "pirn_vectors",
        dimension: int,
        embedder: EmbeddingProvider | None = None,
        batch_size: int = 100,
        credential: CredentialRef | None = None,
        pool: Any | None = None,
    ) -> None:
        """Initialise the pgvector adapter.

        Args:
            dsn: Postgres DSN used to build the connection pool.
            table: Table name holding ``(id, embedding, metadata, document)``.
            dimension: Vector dimension the table's ``vector`` column expects.
            embedder: Optional provider enabling text :meth:`search`.
            batch_size: Rows per ``executemany`` upsert batch. Must be positive.
            credential: Optional credential scrubbed on :meth:`close`.
            pool: Optional pre-built asyncpg-compatible pool; when supplied it is
                reused and no driver import happens (the test seam).

        Raises:
            ValueError: If ``batch_size`` is not a positive int.
        """
        super().__init__(embedder=embedder)
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError(f"batch_size must be a positive int, got {batch_size!r}")
        self._dsn: str = dsn
        self._table: str = table
        self._dimension: int = dimension
        self._batch_size: int = batch_size
        self._credential: CredentialRef | None = credential
        self._pool: Any | None = pool

    async def _get_pool(self) -> Any:
        """Return the connection pool, building it once via ``asyncpg``."""
        if self._pool is None:
            asyncpg = _require("pgvector", "asyncpg")
            self._pool = await asyncpg.create_pool(self._dsn)
        return self._pool

    # --- SQL builders (pure, unit-tested without a database) --------------
    def _upsert_sql(self) -> str:
        """Return the parameterised upsert statement for this table."""
        return (
            f"INSERT INTO {self._table} (id, embedding, metadata, document) "
            "VALUES ($1, $2::vector, $3::jsonb, $4) "
            "ON CONFLICT (id) DO UPDATE SET "
            "embedding = EXCLUDED.embedding, "
            "metadata = EXCLUDED.metadata, "
            "document = EXCLUDED.document"
        )

    def _query_sql(self) -> str:
        """Return the parameterised nearest-neighbour query for this table."""
        return (
            "SELECT id, embedding, metadata, document, "
            "(embedding <=> $1::vector) AS distance "
            f"FROM {self._table} "
            "WHERE ($2::jsonb IS NULL OR metadata @> $2::jsonb) "
            "ORDER BY distance LIMIT $3"
        )

    def _get_sql(self) -> str:
        """Return the parameterised single-record fetch for this table."""
        return f"SELECT id, embedding, metadata, document FROM {self._table} WHERE id = $1"

    def _delete_sql(self) -> str:
        """Return the parameterised bulk-delete statement for this table."""
        return f"DELETE FROM {self._table} WHERE id = ANY($1::text[])"

    @staticmethod
    def _to_vector_literal(vector: Sequence[float]) -> str:
        """Render a vector as pgvector's ``[a,b,c]`` text literal."""
        return "[" + ",".join(repr(float(x)) for x in vector) + "]"

    @staticmethod
    def _parse_vector_literal(literal: str) -> tuple[float, ...]:
        """Parse pgvector's ``[a,b,c]`` text literal back into a tuple."""
        inner = literal.strip().lstrip("[").rstrip("]").strip()
        if not inner:
            return ()
        return tuple(float(part) for part in inner.split(","))

    @staticmethod
    def _filter_to_json(metadata_filter: Mapping[str, Any] | None) -> str | None:
        """Render a scalar-equality metadata filter as a jsonb-containment string.

        Args:
            metadata_filter: Filter mapping, or ``None``.

        Returns:
            A JSON object string for jsonb containment, or ``None`` for no
            filter.

        Raises:
            ValueError: If a non-scalar (list/tuple/set) predicate is given;
                jsonb containment maps only scalar equality.
        """
        if not metadata_filter:
            return None
        for key, expected in metadata_filter.items():
            if isinstance(expected, list | tuple | set):
                raise ValueError(
                    f"PgvectorMemoryStore only supports scalar-equality filters; "
                    f"field {key!r} got a collection {expected!r}"
                )
        return json.dumps(dict(metadata_filter))

    def _iter_batches(self, rows: list[tuple[Any, ...]]) -> Iterator[list[tuple[Any, ...]]]:
        """Yield ``rows`` in contiguous chunks of at most ``batch_size``."""
        for start in range(0, len(rows), self._batch_size):
            yield rows[start : start + self._batch_size]

    # --- vector-native core ----------------------------------------------
    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Batch-upsert ``records`` via ``executemany`` over a pooled connection."""
        rows: list[tuple[Any, ...]] = [
            (
                record.id,
                self._to_vector_literal(record.vector),
                json.dumps(dict(record.metadata)),
                record.document,
            )
            for record in records
        ]
        if not rows:
            return
        pool = await self._get_pool()
        sql = self._upsert_sql()
        async with pool.acquire() as conn:
            for batch in self._iter_batches(rows):
                await conn.executemany(sql, batch)

    async def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 10,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """Return up to ``top_k`` nearest records, ranked server-side by cosine distance."""
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"top_k must be a positive int, got {top_k!r}")
        literal = self._to_vector_literal(vector)
        filter_json = self._filter_to_json(metadata_filter)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(self._query_sql(), literal, filter_json, top_k)
        return [self._row_to_match(row) for row in rows]

    async def get(self, key: str) -> VectorRecord | None:
        """Return the record stored under ``key``, or ``None``."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(self._get_sql(), key)
        if row is None:
            return None
        return self._row_to_record(row)

    async def delete(self, ids: Sequence[str]) -> None:
        """Remove every record whose id is in ``ids``."""
        if not ids:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(self._delete_sql(), list(ids))

    def _row_to_match(self, row: Mapping[str, Any]) -> VectorMatch:
        """Convert a query result row into a :class:`VectorMatch`."""
        return VectorMatch(
            id=row["id"],
            score=1.0 - float(row["distance"]),
            metadata=self._row_metadata(row),
            document=row["document"],
        )

    def _row_to_record(self, row: Mapping[str, Any]) -> VectorRecord:
        """Convert a fetched row into a :class:`VectorRecord`."""
        return VectorRecord(
            id=row["id"],
            vector=self._parse_vector_literal(row["embedding"]),
            metadata=self._row_metadata(row),
            document=row["document"],
        )

    @staticmethod
    def _row_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
        """Decode a row's jsonb metadata column into a dict."""
        raw = row["metadata"]
        if raw is None:
            return {}
        if isinstance(raw, str):
            return dict(json.loads(raw))
        return dict(raw)

    async def close(self) -> None:
        """Close the pool (if built) and scrub credentials."""
        pool = self._pool
        if pool is not None and callable(getattr(pool, "close", None)):
            result = pool.close()
            if hasattr(result, "__await__"):
                await result
        self._pool = None
        self._clear_credentials()

    def _clear_credentials(self) -> None:
        """Drop the credential so the secret becomes GC-able."""
        self._credential = None
