"""ATDD acceptance test: file -> transform -> sqlite, end-to-end in a real
:class:`pirn.tapestry.Tapestry`.

This is the gating test for Layer-2 connector integration. It proves that:

1. ``LocalFilesystemStore`` (Layer 1) plugs into ``ObjectStoreReadSource``
   (Layer 2 :class:`Source`) as a real pirn knot with no parents.
2. A pure-Python ``@knot`` transform converts the bytes payload into row
   tuples — demonstrating the data domain consumes connector output.
3. ``DatabaseExecuteSink`` (Layer 2 :class:`Sink`) writes those rows into
   a ``SqlitePool`` (Layer 1) via the ``DatabaseConnectionPool`` interface.
4. The Tapestry runs to completion under pirn's standard execution +
   lineage machinery — ``RunResult.succeeded`` is True and the SQLite
   table contains the expected rows.

If any of those four things break, this test catches it before the YAML
loader or any user pipeline does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.connectors.knots.database_execute_sink import DatabaseExecuteSink
from pirn.connectors.knots.object_store_read_source import ObjectStoreReadSource
from pirn.connectors.object_storage.local_filesystem_config import (
    LocalFilesystemConfig,
)
from pirn.connectors.object_storage.local_filesystem_store import (
    LocalFilesystemStore,
)
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry


@knot
async def parse_user_records(payload: bytes) -> list[tuple[int, str, str]]:
    """Decode JSON-array payload into (id, name, region) tuples."""
    records = json.loads(payload.decode("utf-8"))
    return [
        (int(r["id"]), str(r["name"]), str(r["region"]))
        for r in records
    ]


@pytest.mark.asyncio
async def test_file_to_sqlite_acceptance_pipeline(tmp_path: Path) -> None:
    # ── Arrange: file in the local store, sqlite table waiting.
    store = LocalFilesystemStore(LocalFilesystemConfig(root=tmp_path / "data"))
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    try:
        await pool.execute(
            "CREATE TABLE users ("
            "  id INTEGER PRIMARY KEY,"
            "  name TEXT NOT NULL,"
            "  region TEXT NOT NULL"
            ")"
        )

        await store.put(
            "users.json",
            json.dumps(
                [
                    {"id": 1, "name": "alice", "region": "EU"},
                    {"id": 2, "name": "bob",   "region": "US"},
                    {"id": 3, "name": "priya", "region": "IN"},
                ]
            ).encode("utf-8"),
        )

        # ── Act: build a real Tapestry and run it.
        with Tapestry() as t:
            payload = ObjectStoreReadSource(
                store=store,
                key="users.json",
                _config=KnotConfig(id="extract"),
            )
            rows = parse_user_records(
                payload=payload, _config=KnotConfig(id="parse")
            )
            DatabaseExecuteSink(
                pool=pool,
                query="INSERT INTO users (id, name, region) VALUES (?, ?, ?)",
                rows=rows,
                _config=KnotConfig(id="load"),
            )

        result = await t.run(RunRequest())

        # ── Assert: pipeline succeeded and the table has the rows.
        assert result.succeeded, [
            (rec.knot_id, rec.outcome) for rec in result.lineage
        ]

        loaded = await pool.fetch_all(
            "SELECT id, name, region FROM users ORDER BY id"
        )
        assert loaded == [
            (1, "alice", "EU"),
            (2, "bob", "US"),
            (3, "priya", "IN"),
        ]

        # All three knots must appear in the lineage with successful outcomes.
        outcomes = {rec.knot_id: rec.outcome for rec in result.lineage}
        assert outcomes["extract"] == "ok"
        assert outcomes["parse"] == "ok"
        assert outcomes["load"] == "ok"
    finally:
        await pool.close()
