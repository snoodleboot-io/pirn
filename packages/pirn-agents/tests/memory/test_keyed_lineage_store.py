"""Tests for :class:`KeyedLineageStore` (ADR "agents speaks core" WS3 part 4).

A keyed identity is a knot id, not a KV slot: these exercise real writes
(each its own single-knot ``Tapestry.run()``) and reads
(``RunHistory.query_latest_lineage_by_knot_id`` + ``DataStore.get``) rather
than mocking the engine.
"""

from __future__ import annotations

import pytest
from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.content_hasher import ContentHasher
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.keyed_lineage_store import KeyedLineageStore


@pytest.fixture
def store() -> KeyedLineageStore:
    return KeyedLineageStore(history=InMemoryHistory(), data_store=InMemoryDataStore())


class TestIdentity:
    def test_joins_namespace_and_key(self) -> None:
        assert KeyedLineageStore.identity("ns", "k1") == "ns:k1"

    def test_rejects_empty_namespace(self) -> None:
        with pytest.raises(ValueError):
            KeyedLineageStore.identity("", "k1")

    def test_rejects_empty_key(self) -> None:
        with pytest.raises(ValueError):
            KeyedLineageStore.identity("ns", "")

    @pytest.mark.parametrize(
        "key",
        ["../../etc/passwd", "a/b/c", "with space", "unicode-ключ", "?*<>|"],
        ids=["traversal", "slashes", "space", "unicode", "wildcards"],
    )
    def test_escapes_filesystem_hostile_keys_into_a_valid_knot_id(self, key: str) -> None:
        identity = KeyedLineageStore.identity("ns", key)
        KnotConfig(id=identity)  # must not raise

    def test_a_colon_inside_a_component_cannot_be_mistaken_for_the_separator(self) -> None:
        # Without escaping the colon *inside* a component, ("a", "b:c") and
        # ("a:b", "c") would collide on the same literal string "a:b:c".
        assert KeyedLineageStore.identity("a", "b:c") != KeyedLineageStore.identity("a:b", "c")

    def test_a_literal_dot_does_not_collide_with_an_escape_sequence(self) -> None:
        # "." is the escape leader, so a caller's own "." must itself be
        # escaped -- otherwise key="." and key="2e" (an already-hex-looking
        # string) could produce indistinguishable output.
        assert KeyedLineageStore.identity("ns", ".") != KeyedLineageStore.identity("ns", "2e")


class TestPutAndGet:
    async def test_get_missing_key_returns_none(self, store: KeyedLineageStore) -> None:
        assert await store.get(namespace="ns", key="absent") is None

    async def test_put_then_get_round_trips(self, store: KeyedLineageStore) -> None:
        await store.put(namespace="ns", key="k1", value={"v": 1})
        assert await store.get(namespace="ns", key="k1") == {"v": 1}

    async def test_put_returns_the_knot_id(self, store: KeyedLineageStore) -> None:
        identity = await store.put(namespace="ns", key="k1", value={"v": 1})
        assert identity == "ns:k1"

    async def test_second_put_overwrites_what_get_returns(self, store: KeyedLineageStore) -> None:
        await store.put(namespace="ns", key="k1", value={"v": 1})
        await store.put(namespace="ns", key="k1", value={"v": 2})
        assert await store.get(namespace="ns", key="k1") == {"v": 2}

    async def test_different_keys_do_not_collide(self, store: KeyedLineageStore) -> None:
        await store.put(namespace="ns", key="a", value={"v": "a"})
        await store.put(namespace="ns", key="b", value={"v": "b"})
        assert await store.get(namespace="ns", key="a") == {"v": "a"}
        assert await store.get(namespace="ns", key="b") == {"v": "b"}

    async def test_different_namespaces_do_not_collide(self, store: KeyedLineageStore) -> None:
        await store.put(namespace="ns1", key="k", value={"v": 1})
        await store.put(namespace="ns2", key="k", value={"v": 2})
        assert await store.get(namespace="ns1", key="k") == {"v": 1}
        assert await store.get(namespace="ns2", key="k") == {"v": 2}

    async def test_every_write_is_its_own_lineage_row(self, store: KeyedLineageStore) -> None:
        await store.put(namespace="ns", key="k1", value={"v": 1})
        await store.put(namespace="ns", key="k1", value={"v": 2})
        rows = await store.history.query_lineage_by_knot_id("ns:k1")
        assert len(rows) == 2


class TestLatestOutputHash:
    async def test_none_when_never_written(self, store: KeyedLineageStore) -> None:
        assert await store.latest_output_hash(namespace="ns", key="absent") is None

    async def test_matches_content_hash_of_the_written_value(
        self, store: KeyedLineageStore
    ) -> None:
        value = {"v": 1}
        await store.put(namespace="ns", key="k1", value=value)
        assert await store.latest_output_hash(namespace="ns", key="k1") == ContentHasher.hash(value)

    async def test_changes_when_the_value_changes(self, store: KeyedLineageStore) -> None:
        await store.put(namespace="ns", key="k1", value={"v": 1})
        first = await store.latest_output_hash(namespace="ns", key="k1")
        await store.put(namespace="ns", key="k1", value={"v": 2})
        second = await store.latest_output_hash(namespace="ns", key="k1")
        assert first != second

    async def test_unchanged_when_the_same_value_is_written_again(
        self, store: KeyedLineageStore
    ) -> None:
        await store.put(namespace="ns", key="k1", value={"v": 1})
        first = await store.latest_output_hash(namespace="ns", key="k1")
        await store.put(namespace="ns", key="k1", value={"v": 1})
        second = await store.latest_output_hash(namespace="ns", key="k1")
        assert first == second


class TestDelete:
    async def test_delete_makes_get_return_none(self, store: KeyedLineageStore) -> None:
        await store.put(namespace="ns", key="k1", value={"v": 1})
        await store.delete(namespace="ns", key="k1")
        assert await store.get(namespace="ns", key="k1") is None

    async def test_delete_of_an_absent_key_is_a_harmless_no_op_write(
        self, store: KeyedLineageStore
    ) -> None:
        await store.delete(namespace="ns", key="never-written")
        assert await store.get(namespace="ns", key="never-written") is None

    async def test_rewriting_after_delete_makes_it_visible_again(
        self, store: KeyedLineageStore
    ) -> None:
        await store.put(namespace="ns", key="k1", value={"v": 1})
        await store.delete(namespace="ns", key="k1")
        await store.put(namespace="ns", key="k1", value={"v": 2})
        assert await store.get(namespace="ns", key="k1") == {"v": 2}

    async def test_history_keeps_every_write_including_the_tombstone(
        self, store: KeyedLineageStore
    ) -> None:
        await store.put(namespace="ns", key="k1", value={"v": 1})
        await store.delete(namespace="ns", key="k1")
        rows = await store.history.query_lineage_by_knot_id("ns:k1")
        assert len(rows) == 2


class TestConstruction:
    def test_rejects_non_run_history(self) -> None:
        with pytest.raises(TypeError):
            KeyedLineageStore(history="bad", data_store=InMemoryDataStore())

    def test_rejects_non_data_store(self) -> None:
        with pytest.raises(TypeError):
            KeyedLineageStore(history=InMemoryHistory(), data_store="bad")
