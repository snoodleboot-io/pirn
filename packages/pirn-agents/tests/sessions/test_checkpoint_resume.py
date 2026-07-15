"""Mirrored tests for the S3 checkpoint/resume knots (PIR-362)."""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.sessions.in_memory_session_store import InMemorySessionStore
from pirn_agents.sessions.run_checkpointer import RunCheckpointer
from pirn_agents.sessions.run_resumer import RunResumer
from pirn_agents.sessions.session_message import SessionMessage
from tests.sessions.conftest import make_run_state


def _checkpointer() -> RunCheckpointer:
    with Tapestry():
        return RunCheckpointer(
            store=InMemorySessionStore(),
            state=make_run_state(),
            _config=KnotConfig(id="cp"),
        )


def _resumer() -> RunResumer:
    with Tapestry():
        return RunResumer(
            store=InMemorySessionStore(),
            session_id="sess-1",
            _config=KnotConfig(id="rz"),
        )


class TestRunCheckpointer:
    async def test_checkpoint_persists_state(self) -> None:
        store = InMemorySessionStore()
        state = make_run_state(session_id="s1", plan=("a", "b"))
        cp = await _checkpointer().process(store=store, state=state)
        assert (await store.load("s1")) == cp

    async def test_identical_state_dedups_without_rewrite(self) -> None:
        store = InMemorySessionStore()
        state = make_run_state(session_id="s1", plan=("a",))
        first = await _checkpointer().process(store=store, state=state)
        second = await _checkpointer().process(store=store, state=state)
        # Same content hash -> the second call returns the already-stored object.
        assert first is second
        assert first.checkpoint_id == second.checkpoint_id

    async def test_changed_state_writes_new_checkpoint(self) -> None:
        store = InMemorySessionStore()
        state = make_run_state(session_id="s1", plan=("a",))
        first = await _checkpointer().process(store=store, state=state)
        changed = state.with_message(SessionMessage(role="user", content="hi"))
        second = await _checkpointer().process(store=store, state=changed)
        assert first.checkpoint_id != second.checkpoint_id
        assert (await store.load("s1")) == second

    async def test_rejects_non_store(self) -> None:
        with pytest.raises(TypeError):
            await _checkpointer().process(store="bad", state=make_run_state())  # type: ignore[arg-type]


class TestRunResumer:
    async def test_resume_rehydrates_state(self) -> None:
        store = InMemorySessionStore()
        state = make_run_state(session_id="s1", plan=("a", "b", "c"), step_index=1)
        await _checkpointer().process(store=store, state=state)
        resumed = await _resumer().process(store=store, session_id="s1")
        assert resumed == state

    async def test_resume_replays_only_uncomputed_tail(self) -> None:
        store = InMemorySessionStore()
        state = make_run_state(session_id="s1", plan=("a", "b", "c"), step_index=2)
        await _checkpointer().process(store=store, state=state)
        resumed = await _resumer().process(store=store, session_id="s1")
        assert resumed is not None
        assert resumed.remaining_plan() == ("c",)

    async def test_resume_missing_returns_none(self) -> None:
        store = InMemorySessionStore()
        assert await _resumer().process(store=store, session_id="ghost") is None

    async def test_repeated_resume_is_idempotent_no_writes(self) -> None:
        store = InMemorySessionStore()
        state = make_run_state(session_id="s1", plan=("a", "b"))
        cp = await _checkpointer().process(store=store, state=state)
        first = await _resumer().process(store=store, session_id="s1")
        second = await _resumer().process(store=store, session_id="s1")
        assert first == second == state
        # Load-only: the stored checkpoint is untouched by resume.
        assert (await store.load("s1")) == cp

    async def test_rejects_empty_session_id(self) -> None:
        with pytest.raises(TypeError):
            await _resumer().process(store=InMemorySessionStore(), session_id="")
