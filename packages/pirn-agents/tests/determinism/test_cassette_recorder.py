"""Mirrored tests for the record/replay/passthrough engine (F29-S1)."""

from __future__ import annotations

import unittest

from pirn_agents.determinism.cassette import Cassette
from pirn_agents.determinism.cassette_recorder import CassetteRecorder
from pirn_agents.determinism.interaction_kind import InteractionKind
from pirn_agents.determinism.recording_mode import RecordingMode
from pirn_agents.exceptions.missing_cassette_entry_error import MissingCassetteEntryError


class _Counter:
    """A thunk factory that counts how many live calls actually happened."""

    def __init__(self, value: object) -> None:
        self.value = value
        self.calls = 0

    async def run(self) -> object:
        self.calls += 1
        return self.value


class RecordModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_records_and_returns_live_output(self) -> None:
        rec = CassetteRecorder(mode=RecordingMode.RECORD)
        counter = _Counter({"answer": 42})
        out = await rec.invoke(key="q1", kind=InteractionKind.LLM, thunk=counter.run)
        assert out == {"answer": 42}
        assert counter.calls == 1
        assert len(rec.cassette.entries) == 1
        assert rec.cassette.entries[0].key == "q1"

    async def test_repeated_key_gets_incrementing_sequence(self) -> None:
        rec = CassetteRecorder(mode=RecordingMode.RECORD)
        await rec.invoke(key="q", kind=InteractionKind.TOOL, thunk=_Counter("a").run)
        await rec.invoke(key="q", kind=InteractionKind.TOOL, thunk=_Counter("b").run)
        seqs = [e.sequence for e in rec.cassette.entries_for("q")]
        assert seqs == [0, 1]


class ReplayModeTests(unittest.IsolatedAsyncioTestCase):
    async def _recorded_tape(self) -> Cassette:
        rec = CassetteRecorder(mode=RecordingMode.RECORD)
        await rec.invoke(key="q1", kind=InteractionKind.LLM, thunk=_Counter("first").run)
        await rec.invoke(key="q1", kind=InteractionKind.LLM, thunk=_Counter("second").run)
        return rec.cassette

    async def test_replays_without_live_call(self) -> None:
        tape = await self._recorded_tape()
        rec = CassetteRecorder(cassette=tape, mode=RecordingMode.REPLAY)
        counter = _Counter("SHOULD NOT RUN")
        first = await rec.invoke(key="q1", kind=InteractionKind.LLM, thunk=counter.run)
        second = await rec.invoke(key="q1", kind=InteractionKind.LLM, thunk=counter.run)
        assert first == "first"
        assert second == "second"
        assert counter.calls == 0

    async def test_missing_entry_raises_clear_error(self) -> None:
        rec = CassetteRecorder(cassette=Cassette(), mode=RecordingMode.REPLAY)
        with self.assertRaises(MissingCassetteEntryError) as ctx:
            await rec.invoke(key="absent", kind=InteractionKind.RETRIEVAL, thunk=_Counter(1).run)
        assert ctx.exception.key == "absent"
        assert ctx.exception.kind == "retrieval"

    async def test_exhausted_key_raises(self) -> None:
        tape = await self._recorded_tape()
        rec = CassetteRecorder(cassette=tape, mode=RecordingMode.REPLAY)
        await rec.invoke(key="q1", kind=InteractionKind.LLM, thunk=_Counter("x").run)
        await rec.invoke(key="q1", kind=InteractionKind.LLM, thunk=_Counter("x").run)
        with self.assertRaises(MissingCassetteEntryError):
            await rec.invoke(key="q1", kind=InteractionKind.LLM, thunk=_Counter("x").run)


class PassthroughModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_live_and_records_nothing(self) -> None:
        rec = CassetteRecorder(mode=RecordingMode.PASSTHROUGH)
        counter = _Counter("live")
        out = await rec.invoke(key="q", kind=InteractionKind.GENERIC, thunk=counter.run)
        assert out == "live"
        assert counter.calls == 1
        assert rec.cassette.is_empty


class ConstructionTests(unittest.TestCase):
    def test_rejects_non_cassette(self) -> None:
        with self.assertRaises(TypeError):
            CassetteRecorder(cassette=object(), mode=RecordingMode.RECORD)  # type: ignore[arg-type]

    def test_rejects_non_mode(self) -> None:
        with self.assertRaises(TypeError):
            CassetteRecorder(mode="record")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
