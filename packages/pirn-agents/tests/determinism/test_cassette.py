"""Mirrored tests for the cassette data model and stores (F29-S1)."""

from __future__ import annotations

import unittest

from pirn_agents.determinism.cassette import Cassette
from pirn_agents.determinism.cassette_entry import CassetteEntry
from pirn_agents.determinism.in_memory_cassette_store import InMemoryCassetteStore
from pirn_agents.determinism.interaction_kind import InteractionKind


def _entry(key: str = "k1", sequence: int = 0) -> CassetteEntry:
    return CassetteEntry(
        key=key,
        kind=InteractionKind.LLM,
        output={"content": "hello"},
        sequence=sequence,
    )


class CassetteEntryTests(unittest.TestCase):
    def test_round_trips_without_loss(self) -> None:
        entry = _entry()
        assert CassetteEntry.from_payload(entry.to_payload()) == entry

    def test_key_for_is_stable_content_digest(self) -> None:
        first = CassetteEntry.key_for({"a": 1, "b": 2})
        second = CassetteEntry.key_for({"b": 2, "a": 1})
        assert first == second
        assert first != CassetteEntry.key_for({"a": 1, "b": 3})

    def test_rejects_empty_key(self) -> None:
        with self.assertRaises(TypeError):
            CassetteEntry(key="", kind=InteractionKind.TOOL, output=None)

    def test_rejects_non_kind(self) -> None:
        with self.assertRaises(TypeError):
            CassetteEntry(key="k", kind="llm", output=None)  # type: ignore[arg-type]

    def test_rejects_negative_sequence(self) -> None:
        with self.assertRaises(ValueError):
            _entry(sequence=-1)


class CassetteTests(unittest.TestCase):
    def test_empty_by_default(self) -> None:
        assert Cassette().is_empty

    def test_with_entry_is_immutable_append(self) -> None:
        base = Cassette()
        extended = base.with_entry(_entry())
        assert base.is_empty
        assert len(extended.entries) == 1

    def test_entries_for_and_keys(self) -> None:
        tape = Cassette().with_entry(_entry("a")).with_entry(_entry("b")).with_entry(_entry("a", 1))
        assert tape.keys() == ("a", "b")
        assert len(tape.entries_for("a")) == 2

    def test_round_trips_without_loss(self) -> None:
        tape = Cassette().with_entry(_entry("a")).with_entry(_entry("b"))
        assert Cassette.from_payload(tape.to_payload()) == tape

    def test_rejects_non_entry_member(self) -> None:
        with self.assertRaises(TypeError):
            Cassette(entries=("bad",))  # type: ignore[arg-type]


class InMemoryCassetteStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_load_list_delete(self) -> None:
        store = InMemoryCassetteStore()
        tape = Cassette().with_entry(_entry())
        await store.save("suite", tape)
        assert await store.load("suite") == tape
        assert list(await store.list_cassettes()) == ["suite"]
        await store.delete("suite")
        assert await store.load("suite") is None

    async def test_load_missing_returns_none(self) -> None:
        assert await InMemoryCassetteStore().load("nope") is None

    async def test_save_rejects_non_cassette(self) -> None:
        with self.assertRaises(TypeError):
            await InMemoryCassetteStore().save("x", object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
