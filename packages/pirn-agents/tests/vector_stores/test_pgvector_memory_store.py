"""Tests for :class:`PgvectorMemoryStore`.

Three layers, none needing a real database by default:

* the full shared conformance suite, run against a faithful in-memory
  ``asyncpg`` pool double that honours the adapter's actual SQL;
* pure unit tests for the SQL builders and the metadata-filter -> jsonb mapping;
* a ``needs_pgvector`` case that runs the same conformance intent against a real
  pgvector database when one is configured (skipped otherwise).
"""

from __future__ import annotations

import json
import os
import unittest

import numpy as np
import pytest

from pirn_agents.vector_stores.pgvector_memory_store import PgvectorMemoryStore
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore
from tests.vector_stores.conformance import FixedEmbedder, VectorStoreConformance


class FakePgConn:
    """An in-memory asyncpg-connection double honouring the adapter's SQL."""

    def __init__(self, rows: dict[str, dict[str, object]]) -> None:
        self._rows = rows

    async def executemany(self, sql: str, args_iter: list[tuple[object, ...]]) -> None:
        assert "insert into" in sql.lower()
        for identifier, literal, metadata_json, document in args_iter:
            self._rows[str(identifier)] = {
                "id": identifier,
                "embedding": literal,
                "metadata": metadata_json,
                "document": document,
            }

    async def execute(self, sql: str, arg: list[str]) -> None:
        assert "delete" in sql.lower()
        for identifier in arg:
            self._rows.pop(str(identifier), None)

    async def fetchrow(self, sql: str, key: str) -> dict[str, object] | None:
        assert "where id = $1" in sql.lower()
        row = self._rows.get(str(key))
        return dict(row) if row is not None else None

    async def fetch(
        self, sql: str, literal: str, filter_json: str | None, top_k: int
    ) -> list[dict[str, object]]:
        assert "order by distance" in sql.lower()
        query = np.asarray(_parse(literal), dtype=np.float64)
        query_norm = float(np.linalg.norm(query)) or 1.0
        wanted = json.loads(filter_json) if filter_json is not None else None
        scored: list[tuple[float, dict[str, object]]] = []
        for row in self._rows.values():
            metadata = json.loads(str(row["metadata"]))
            if wanted is not None and any(metadata.get(k) != v for k, v in wanted.items()):
                continue
            candidate = np.asarray(_parse(str(row["embedding"])), dtype=np.float64)
            denom = (float(np.linalg.norm(candidate)) or 1.0) * query_norm
            distance = 1.0 - float(candidate @ query) / denom
            out = dict(row)
            out["distance"] = distance
            scored.append((distance, out))
        scored.sort(key=lambda pair: pair[0])
        return [row for _, row in scored[:top_k]]


class _Acquire:
    """Async-context-manager wrapper mirroring ``pool.acquire()``."""

    def __init__(self, conn: FakePgConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakePgConn:
        return self._conn

    async def __aexit__(self, *exc: object) -> None:
        return None


class FakePgPool:
    """An in-memory asyncpg-pool double sharing one connection's rows."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}
        self.closed = False

    def acquire(self) -> _Acquire:
        return _Acquire(FakePgConn(self.rows))

    def close(self) -> None:
        self.closed = True


def _parse(literal: str) -> list[float]:
    inner = literal.strip().lstrip("[").rstrip("]").strip()
    return [float(part) for part in inner.split(",")] if inner else []


class TestPgvectorConformance(VectorStoreConformance):
    async def make_store(self) -> VectorMemoryStore:
        return PgvectorMemoryStore(
            dsn="postgresql://stub",
            dimension=3,
            embedder=FixedEmbedder([1.0, 0.0, 0.0]),
            pool=FakePgPool(),
        )


class TestPgvectorSqlBuilders(unittest.TestCase):
    def setUp(self) -> None:
        self.store = PgvectorMemoryStore(dsn="postgresql://x", dimension=3, table="vecs")

    def test_upsert_sql_targets_table_and_upserts(self) -> None:
        sql = self.store._upsert_sql()
        assert "INSERT INTO vecs" in sql
        assert "ON CONFLICT (id) DO UPDATE" in sql

    def test_query_sql_uses_cosine_operator_and_filter(self) -> None:
        sql = self.store._query_sql()
        assert "<=>" in sql
        assert "metadata @> $2::jsonb" in sql
        assert "LIMIT $3" in sql

    def test_delete_sql_uses_array_predicate(self) -> None:
        assert "id = ANY($1::text[])" in self.store._delete_sql()

    def test_vector_literal_roundtrips(self) -> None:
        literal = self.store._to_vector_literal([1.0, 2.5, -3.0])
        assert self.store._parse_vector_literal(literal) == (1.0, 2.5, -3.0)

    def test_scalar_filter_maps_to_json(self) -> None:
        assert self.store._filter_to_json({"kind": "x"}) == json.dumps({"kind": "x"})
        assert self.store._filter_to_json(None) is None

    def test_collection_filter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.store._filter_to_json({"kind": ["x", "y"]})


class TestPgvectorBatching(unittest.IsolatedAsyncioTestCase):
    async def test_upsert_batches_use_executemany(self) -> None:
        from pirn_agents.vector_stores.vector_record import VectorRecord

        pool = FakePgPool()
        store = PgvectorMemoryStore(dsn="postgresql://x", dimension=2, batch_size=2, pool=pool)
        await store.upsert(
            [VectorRecord.create(id=str(i), vector=[float(i), 0.0]) for i in range(5)]
        )
        assert len(pool.rows) == 5

    async def test_close_closes_pool(self) -> None:
        pool = FakePgPool()
        store = PgvectorMemoryStore(dsn="postgresql://x", dimension=2, pool=pool)
        await store.close()
        assert pool.closed is True


@pytest.mark.needs_pgvector
class TestPgvectorRealBackend(unittest.IsolatedAsyncioTestCase):
    async def test_conformance_against_real_pgvector(self) -> None:
        dsn = os.environ.get("PIRN_TEST_PGVECTOR_URL")
        if not dsn:
            self.skipTest("PIRN_TEST_PGVECTOR_URL not set")
        store = PgvectorMemoryStore(dsn=dsn, dimension=3, embedder=FixedEmbedder([1.0, 0.0, 0.0]))
        from pirn_agents.vector_stores.vector_record import VectorRecord

        await store.upsert([VectorRecord.create(id="a", vector=[1.0, 0.0, 0.0])])
        matches = await store.query([1.0, 0.0, 0.0], top_k=1)
        assert matches and matches[0].id == "a"
        await store.close()


if __name__ == "__main__":
    unittest.main()
