"""Mirrored tests for the stdlib-JSON file cassette store (F29-S1)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn_agents.determinism.cassette import Cassette
from pirn_agents.determinism.cassette_entry import CassetteEntry
from pirn_agents.determinism.file_cassette_store import FileCassetteStore
from pirn_agents.determinism.interaction_kind import InteractionKind


def _tape() -> Cassette:
    return Cassette().with_entry(
        CassetteEntry(key="k1", kind=InteractionKind.LLM, output={"content": "hi"})
    )


class FileCassetteStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_round_trips_through_disk(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            store = FileCassetteStore(root)
            await store.save("suite", _tape())
            assert await store.load("suite") == _tape()
            assert (Path(root) / "suite.json").is_file()

    async def test_load_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            assert await FileCassetteStore(root).load("nope") is None

    async def test_list_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            store = FileCassetteStore(root)
            await store.save("a", _tape())
            await store.save("b", _tape())
            assert list(await store.list_cassettes()) == ["a", "b"]
            await store.delete("a")
            assert list(await store.list_cassettes()) == ["b"]

    async def test_sanitises_unsafe_names(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            store = FileCassetteStore(root)
            await store.save("a/b:c", _tape())
            assert await store.load("a/b:c") == _tape()

    async def test_save_rejects_non_cassette(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(TypeError):
                await FileCassetteStore(root).save("x", object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
