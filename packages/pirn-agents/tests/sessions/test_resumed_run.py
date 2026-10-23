"""``ResumedRun`` / ``RunResumer`` (PIR-874)."""

from __future__ import annotations

from typing import Any

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.payload import Payload
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

from pirn_agents.sessions.resumed_run import ResumedRun
from pirn_agents.sessions.resumed_run_frame import ResumedRunFrame
from pirn_agents.sessions.run_resumer import RunResumer
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_chain import SessionChain
from pirn_agents.sessions.session_message import SessionMessage


class _MessageSource(Source):
    def __init__(self, *, _config: KnotConfig) -> None:
        super().__init__(_config=_config)

    async def process(self, **_: Any) -> SessionMessage:
        return SessionMessage(role="user", content="hi")


async def _record_turn(history: InMemoryHistory, *, session_id: str, previous: str | None) -> str:
    with Tapestry(history=history) as tapestry:
        _MessageSource(_config=KnotConfig(id="session_message"))
        request = RunRequest(run_id=session_id) if previous is None else RunRequest()
        result = await SessionChain.run_turn(
            tapestry, request, session_id=session_id, previous_run_id=previous
        )
    assert result.succeeded
    return result.run_id


async def _resume(history: InMemoryHistory, session_id: str) -> ResumedRun:
    resumer = RunResumer(history=history, session_id=session_id, _config=KnotConfig(id="r"))
    return await resumer.process(history=history, session_id=session_id)


class TestRunResumer:
    async def test_found_session(self) -> None:
        history = InMemoryHistory()
        first = await _record_turn(history, session_id="s1", previous=None)
        await _record_turn(history, session_id="s1", previous=first)
        resumed = await _resume(history, "s1")
        assert isinstance(resumed, Payload)
        assert isinstance(resumed.metadata, ResumedRunFrame)
        assert resumed.metadata.session_id == "s1"
        assert resumed.metadata.found is True
        assert resumed.metadata.turn_count == 2
        assert isinstance(resumed.data, RunState)
        assert resumed.data.session_id == "s1"

    async def test_absent_session_is_none_data_not_none(self) -> None:
        resumed = await _resume(InMemoryHistory(), "missing")
        assert isinstance(resumed, ResumedRun)
        assert resumed.data is None
        assert resumed.metadata.found is False
        assert resumed.metadata.turn_count == 0


class TestResumedRun:
    def test_audit_dict_has_both_halves(self) -> None:
        state = RunState.from_chain(session_id="s1", turns=())
        audit = ResumedRun(session_id="s1", state=state, turn_count=0)._pirn_audit_dict()
        assert audit["found"] is True
        assert audit["state"] == state.to_payload()

    def test_audit_dict_when_absent(self) -> None:
        audit = ResumedRun(session_id="s1", state=None, turn_count=0)._pirn_audit_dict()
        assert audit["found"] is False
        assert audit["state"] is None

    def test_equality_is_structural(self) -> None:
        a = ResumedRun(session_id="s1", state=None, turn_count=0)
        assert a == ResumedRun(session_id="s1", state=None, turn_count=0)
        assert a != ResumedRun(session_id="s2", state=None, turn_count=0)
