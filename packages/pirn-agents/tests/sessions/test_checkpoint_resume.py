"""Mirrored tests for the S3 checkpoint/resume knots (PIR-362).

``RunCheckpointer`` (a deprecated shim, see the module docstring) is
unchanged. ``RunResumer`` was rewritten for ADR "agents speaks core" WS3 part
2: it rehydrates the session's current ``RunState`` from its run chain
(``SessionChain``/``RunHistory``) rather than loading a stored
``RunCheckpoint`` from a ``SessionStore`` — see ``test_session_chain.py`` for
the chain-walking mechanics and ``test_approval_resume_flow.py`` for the HITL
suspend/resume flow this pairs with.
"""

from __future__ import annotations

from typing import Any

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

from pirn_agents.sessions.in_memory_session_store import InMemorySessionStore
from pirn_agents.sessions.run_checkpointer import RunCheckpointer
from pirn_agents.sessions.run_resumer import RunResumer
from pirn_agents.sessions.session_chain import SessionChain
from pirn_agents.sessions.session_message import SessionMessage
from tests.sessions.conftest import make_run_state


class _MessageSource(Source):
    """Test turn knot: returns a canned session message under a fixed id."""

    def __init__(self, *, message: SessionMessage, _config: KnotConfig) -> None:
        super().__init__(_config=_config)
        self._mutable_message = message

    async def process(self, **_: Any) -> SessionMessage:
        return self._mutable_message


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
            history=InMemoryHistory(),
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
        result = await _checkpointer()({"store": "bad", "state": make_run_state()})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"


async def _run_turn(history: InMemoryHistory, *, session_id: str, previous_run_id, text: str):
    """Run one real turn (a single message-producing Source) via SessionChain."""
    with Tapestry(history=history) as tapestry:
        _MessageSource(
            message=SessionMessage(role="user", content=text),
            _config=KnotConfig(id="session_message"),
        )
        result = await SessionChain.run_turn(
            tapestry, RunRequest(), session_id=session_id, previous_run_id=previous_run_id
        )
    assert result.succeeded
    return result


class TestRunResumer:
    async def test_resume_rehydrates_state_from_the_run_chain(self) -> None:
        history = InMemoryHistory()
        first = await _run_turn(history, session_id="s1", previous_run_id=None, text="hi")
        await _run_turn(history, session_id="s1", previous_run_id=first.run_id, text="again")

        resumed = await _resumer().process(history=history, session_id=first.run_id)

        assert resumed is not None
        assert [m.content for m in resumed.messages] == ["hi", "again"]

    async def test_resume_missing_returns_none(self) -> None:
        history = InMemoryHistory()
        assert await _resumer().process(history=history, session_id="ghost") is None

    async def test_repeated_resume_is_idempotent_no_writes(self) -> None:
        history = InMemoryHistory()
        first = await _run_turn(history, session_id="s1", previous_run_id=None, text="hi")

        one = await _resumer().process(history=history, session_id=first.run_id)
        two = await _resumer().process(history=history, session_id=first.run_id)

        assert one == two

    async def test_rejects_empty_session_id(self) -> None:
        try:
            await _resumer().process(history=InMemoryHistory(), session_id="")
        except TypeError:
            pass
        else:
            raise AssertionError("expected TypeError")
