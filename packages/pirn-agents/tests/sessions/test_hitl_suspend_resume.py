"""Mirrored tests for the S4 HITL suspend/resume flow (PIR-367)."""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.sessions.approval_resumer import ApprovalResumer
from pirn_agents.sessions.human_decision import HumanDecision
from pirn_agents.sessions.in_memory_session_store import InMemorySessionStore
from pirn_agents.sessions.resume_token import ResumeToken
from pirn_agents.sessions.session_store import SessionStore
from pirn_agents.sessions.suspend_signal import SuspendSignal
from pirn_agents.sessions.suspending_approval_check import SuspendingApprovalCheck
from pirn_agents.specializations.human_in_the_loop.approval_check import ApprovalCheck
from pirn_agents.types.agent_response import AgentResponse
from tests.sessions.conftest import make_run_state


def _suspender() -> SuspendingApprovalCheck:
    with Tapestry():
        return SuspendingApprovalCheck(
            response=AgentResponse(content="please approve"),
            store=InMemorySessionStore(),
            state=make_run_state(),
            _config=KnotConfig(id="sac"),
        )


def _resumer() -> ApprovalResumer:
    # Config values are placeholders; every test overrides them via process kwargs.
    with Tapestry():
        return ApprovalResumer(
            store=InMemorySessionStore(),
            token=ResumeToken(session_id="sess-1", checkpoint_id="0" * 64),
            decision=HumanDecision(approved=True),
            _config=KnotConfig(id="ar"),
        )


async def _suspend(store: SessionStore) -> SuspendSignal:
    signal = await _suspender().process(
        response=AgentResponse(content="please approve"),
        store=store,
        state=make_run_state(session_id="sess-1", plan=("a", "b")),
    )
    assert isinstance(signal, SuspendSignal)
    return signal


class TestSuspend:
    async def test_pause_emits_persisted_resumable_token(self) -> None:
        store = InMemorySessionStore()
        signal = await _suspend(store)
        # A resumable token that points at a persisted checkpoint.
        stored = await store.load("sess-1")
        assert stored is not None
        assert signal.token.session_id == "sess-1"
        assert signal.token.checkpoint_id == stored.checkpoint_id
        # The pending response was recorded into the persisted state.
        assert stored.state.messages[-1].role == "approval_request"

    async def test_auto_approve_does_not_suspend(self) -> None:
        store = InMemorySessionStore()
        result = await _suspender().process(
            response=AgentResponse(content="x"),
            store=store,
            state=make_run_state(session_id="sess-1"),
            auto_approve=True,
        )
        assert result is None
        assert await store.load("sess-1") is None

    async def test_rejects_non_response(self) -> None:
        with pytest.raises(TypeError):
            await _suspender().process(
                response="bad",  # type: ignore[arg-type]
                store=InMemorySessionStore(),
                state=make_run_state(),
            )


class TestResume:
    async def test_resume_injects_decision_and_continues(self) -> None:
        store = InMemorySessionStore()
        signal = await _suspend(store)
        resumed = await _resumer().process(
            store=store,
            token=signal.token,
            decision=HumanDecision(approved=True, note="ok", decided_by="ada"),
        )
        assert resumed.messages[-1].role == "approval_decision"
        assert resumed.messages[-1].content.startswith("approved")
        # The uncomputed tail is preserved for the run to continue.
        assert resumed.remaining_plan() == ("a", "b")

    async def test_rejected_decision_recorded(self) -> None:
        store = InMemorySessionStore()
        signal = await _suspend(store)
        resumed = await _resumer().process(
            store=store,
            token=signal.token,
            decision=HumanDecision(approved=False, note="nope"),
        )
        assert resumed.messages[-1].content.startswith("rejected")

    async def test_stale_token_rejected_no_double_injection(self) -> None:
        store = InMemorySessionStore()
        signal = await _suspend(store)
        await _resumer().process(
            store=store, token=signal.token, decision=HumanDecision(approved=True)
        )
        # Re-using the now-stale token must not inject the decision twice.
        with pytest.raises(ValueError, match="stale resume token"):
            await _resumer().process(
                store=store, token=signal.token, decision=HumanDecision(approved=True)
            )

    async def test_unknown_session_rejected(self) -> None:
        store = InMemorySessionStore()
        with pytest.raises(ValueError, match="no suspended run"):
            await _resumer().process(
                store=store,
                token=ResumeToken(session_id="ghost", checkpoint_id="0" * 64),
                decision=HumanDecision(approved=True),
            )


class TestCoexistsWithInRunGating:
    async def test_in_run_approval_check_unbroken(self) -> None:
        # The existing in-run ApprovalCheck still gates by bool, unchanged.
        with Tapestry():
            check = ApprovalCheck(
                response=AgentResponse(content="x"),
                _config=KnotConfig(id="ac"),
            )
        assert await check.process(response=AgentResponse(content="x"), auto_approve=True) is True
        assert await check.process(response=AgentResponse(content="x")) is False
