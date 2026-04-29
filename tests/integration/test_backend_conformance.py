"""Protocol-conformance tests for backends.

Each backend that runs in-process (no server required) is tested against
the same scenarios.  Server-backed backends (Postgres, ValKey, real S3)
are gated by ``@pytest.mark.needs_*`` markers and skip by default.

The conformance contract:

* ``TapestryStore``: register / get / all / snapshot, with the
  duplicate-id-with-different-instance error case.
* ``RunHistory``: record_run / get_run / lineage queries by output
  hash, input hash, and knot id.
* ``DataStore``: put / get / has / scrub, with KeyError on missing
  get.

All three protocols also run the **same end-to-end pipeline** and
verify that lineage reconstructs across backends — i.e., the same run
produces the same output hashes regardless of which backend stored
them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pirn import (
    KnotConfig,
    Parameter,
    RunRequest,
    Tapestry,
    knot,
)
from pirn.backends import DataStore, RunHistory, TapestryStore
from pirn.backends.in_memory import (
    InMemoryDataStore,
    InMemoryHistory,
    InMemoryStore,
)

# --------------------------------------------------- backend factories
#
# Each factory returns a freshly-built backend.  Parametrization over
# these factories runs the same conformance scenario against every
# backend.


def _in_memory_store() -> TapestryStore:
    return InMemoryStore()


def _in_memory_history() -> RunHistory:
    return InMemoryHistory()


def _in_memory_data_store() -> DataStore:
    return InMemoryDataStore()


def _sqlite_store() -> TapestryStore:
    from pirn.backends.sqlite import SQLiteStore

    return SQLiteStore(path=":memory:")


def _sqlite_history() -> RunHistory:
    from pirn.backends.sqlite import SQLiteHistory

    return SQLiteHistory(path=":memory:")


def _duckdb_history() -> RunHistory:
    pytest.importorskip("duckdb")
    from pirn.backends.duckdb import DuckDBHistory

    return DuckDBHistory(path=":memory:")


def _disk_data_store(tmp_path: Path) -> DataStore:
    from pirn.backends.disk import LocalDiskDataStore

    return LocalDiskDataStore(tmp_path)


# --------------------------------------------------- TapestryStore tests


@pytest.fixture(params=[_in_memory_store, _sqlite_store])
def store(request) -> TapestryStore:
    return request.param()


@knot
async def _f(x: int) -> int:
    return x


def test_store_register_and_get(store):
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    # We're not using a Tapestry context here — register manually so the
    # test exercises the store's API directly.
    store.register(p)
    assert store.get("px") is p
    assert store.get("nope") is None


def test_store_all_returns_registered(store):
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    q = Parameter("y", int, _config=KnotConfig(id="py"))
    store.register(p)
    store.register(q)
    ids = sorted(k.knot_id for k in store.all())
    assert ids == ["px", "py"]


def test_store_snapshot_lists_ids(store):
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    store.register(p)
    snap = store.snapshot()
    assert "px" in snap.knot_ids


def test_store_idempotent_same_instance(store):
    p = Parameter("x", int, _config=KnotConfig(id="px"))
    store.register(p)
    store.register(p)  # should not raise
    assert len(store.all()) == 1


def test_store_rejects_duplicate_id_different_instance(store):
    p1 = Parameter("x", int, _config=KnotConfig(id="dup"))
    store.register(p1)
    p2 = Parameter("y", int, _config=KnotConfig(id="dup"))
    with pytest.raises(ValueError, match="already registered"):
        store.register(p2)


# --------------------------------------------------- RunHistory tests


@pytest.fixture(params=[_in_memory_history, _sqlite_history, _duckdb_history])
def history(request) -> RunHistory:
    return request.param()


async def _run_pipeline(history: RunHistory, value: int) -> Any:
    """Run a tiny pipeline against the given history and return the result."""
    with Tapestry(history=history) as t:
        p = Parameter("x", int, _config=KnotConfig(id="x"))
        d = _f(x=p, _config=KnotConfig(id="d"))
    return await t.run(RunRequest(parameters={"x": value}))


async def test_history_record_and_fetch_run(history):
    result = await _run_pipeline(history, 5)
    fetched = await history.get_run(result.run_id)
    assert fetched is not None
    assert fetched.run_id == result.run_id
    assert fetched.outputs == result.outputs


async def test_history_returns_none_for_unknown_run(history):
    fetched = await history.get_run("does-not-exist")
    assert fetched is None


async def test_history_query_by_knot_id_across_runs(history):
    await _run_pipeline(history, 1)
    await _run_pipeline(history, 2)
    matches = await history.query_lineage_by_knot_id("d")
    assert len(matches) == 2


async def test_history_query_by_output_hash_finds_duplicates(history):
    """Two runs with the same input produce the same output hash and
    must be findable by that hash."""
    r1 = await _run_pipeline(history, 5)
    await _run_pipeline(history, 5)
    target = next(rec.output_hash for rec in r1.lineage if rec.knot_id == "d")
    matches = await history.query_lineage_by_output_hash(target)
    # Both runs of d should share this hash.
    d_records = [m for m in matches if m.knot_id == "d"]
    assert len(d_records) == 2


async def test_history_query_by_input_hash_finds_consumers(history):
    """A value produced in run A and consumed in run B is reachable by
    input-hash query."""
    r1 = await _run_pipeline(history, 4)
    r2 = await _run_pipeline(history, 4)
    # The d-knot in both runs consumed the same input (param x = 4 →
    # same hash).
    x_hash_r1 = next(rec.output_hash for rec in r1.lineage if rec.knot_id == "x")
    x_hash_r2 = next(rec.output_hash for rec in r2.lineage if rec.knot_id == "x")
    assert x_hash_r1 == x_hash_r2
    consumers = await history.query_lineage_by_input_hash(x_hash_r1)
    consumer_ids = {c.knot_id for c in consumers}
    assert "d" in consumer_ids


# --------------------------------------------------- DataStore tests


@pytest.fixture
def data_store(request, tmp_path: Path) -> DataStore:
    """Parametrize without using request.param so we can pass tmp_path
    for the disk store.  Driven by an indirect fixture below."""
    factory = request.param
    if factory is _disk_data_store:
        return factory(tmp_path)
    return factory()


@pytest.mark.parametrize(
    "data_store",
    [_in_memory_data_store, _disk_data_store],
    indirect=True,
)
async def test_data_store_put_and_get(data_store):
    await data_store.put("sha256:hello", {"x": 1})
    assert await data_store.get("sha256:hello") == {"x": 1}


@pytest.mark.parametrize(
    "data_store",
    [_in_memory_data_store, _disk_data_store],
    indirect=True,
)
async def test_data_store_has_reflects_presence(data_store):
    assert not await data_store.has("sha256:abc")
    await data_store.put("sha256:abc", 42)
    assert await data_store.has("sha256:abc")


@pytest.mark.parametrize(
    "data_store",
    [_in_memory_data_store, _disk_data_store],
    indirect=True,
)
async def test_data_store_scrub_removes(data_store):
    await data_store.put("sha256:gone", 1)
    await data_store.scrub("sha256:gone")
    assert not await data_store.has("sha256:gone")


@pytest.mark.parametrize(
    "data_store",
    [_in_memory_data_store, _disk_data_store],
    indirect=True,
)
async def test_data_store_get_missing_raises_keyerror(data_store):
    with pytest.raises(KeyError):
        await data_store.get("sha256:nope")


@pytest.mark.parametrize(
    "data_store",
    [_in_memory_data_store, _disk_data_store],
    indirect=True,
)
async def test_data_store_overwrite(data_store):
    await data_store.put("sha256:k", "first")
    await data_store.put("sha256:k", "second")
    assert await data_store.get("sha256:k") == "second"


# ------------------------------------ Cross-backend hash determinism


async def test_lineage_hashes_stable_across_backends():
    """The same pipeline run against InMemory vs SQLite vs DuckDB
    produces the same content hashes — that's the whole point of
    content addressing."""

    async def collect_hashes(history_factory):
        history = history_factory()
        result = await _run_pipeline(history, 7)
        return {rec.knot_id: rec.output_hash for rec in result.lineage}

    pytest.importorskip("duckdb")
    in_mem = await collect_hashes(InMemoryHistory)
    from pirn.backends.sqlite import SQLiteHistory

    sqlite = await collect_hashes(SQLiteHistory)
    from pirn.backends.duckdb import DuckDBHistory

    duck = await collect_hashes(DuckDBHistory)

    assert in_mem == sqlite == duck
