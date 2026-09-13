"""End-to-end HITL suspend/resume: ADR "agents speaks core" WS3 part 2.

Exercises the whole real flow over real ``Tapestry.run()`` calls sharing one
``InMemoryHistory``/``InMemoryDataStore`` pair: a run suspends at
``SuspendingApprovalCheck``, ``SuspendSignal.from_run_result`` reads back the
resumable token, and ``ApprovalResumer`` replays the suspended prefix and
runs a genuinely new downstream knot for the first time with the operator's
decision bound as a ``Parameter``.
"""

from __future__ import annotations

from typing import Any

import pytest
from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.sessions.approval_resumer import ApprovalResumer
from pirn_agents.sessions.human_decision import HumanDecision
from pirn_agents.sessions.human_decision_identity_resolver import HumanDecisionIdentityResolver
from pirn_agents.sessions.resume_token import ResumeToken
from pirn_agents.sessions.suspend_signal import SuspendSignal
from pirn_agents.sessions.suspending_approval_check import SuspendingApprovalCheck
from pirn_agents.types.messaging.agent_response import AgentResponse


class Finalize(Knot):
    """Stands in for "whatever happens after the human decides"."""

    def __init__(self, *, response: Knot, decision: Knot, **kwargs: Any) -> None:
        super().__init__(response=response, decision=decision, **kwargs)

    async def process(self, response: AgentResponse, decision: HumanDecision, **_: Any) -> str:
        verdict = "approved" if decision.approved else "rejected"
        return f"{verdict}:{response.content}"


_RESPONSE = AgentResponse(content="delete the production database")


def _build_suspending_tapestry(history: InMemoryHistory, data_store: InMemoryDataStore) -> Tapestry:
    tapestry = Tapestry(history=history, data_store=data_store)
    with tapestry:
        response = Parameter(name="response", type_=AgentResponse)
        SuspendingApprovalCheck(response=response, _config=KnotConfig(id="gate"))
    return tapestry


class TestSuspendingApprovalCheck:
    async def test_suspends_and_is_absent_from_outputs(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        tapestry = _build_suspending_tapestry(history, data_store)

        result = await tapestry.run(RunRequest(parameters={"response": _RESPONSE}))

        assert result.succeeded
        assert "gate" not in result.outputs
        assert "gate" in result.skipped

    async def test_auto_approve_passes_through(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        with Tapestry(history=history, data_store=data_store) as tapestry:
            response = Parameter(name="response", type_=AgentResponse)
            SuspendingApprovalCheck(
                response=response, auto_approve=True, _config=KnotConfig(id="gate")
            )
        result = await tapestry.run(RunRequest(parameters={"response": _RESPONSE}))
        assert result.succeeded
        assert result.outputs["gate"] == _RESPONSE


class TestSuspendSignalFromRunResult:
    async def test_reads_back_a_resumable_token(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        tapestry = _build_suspending_tapestry(history, data_store)
        result = await tapestry.run(RunRequest(parameters={"response": _RESPONSE}))

        signal = SuspendSignal.from_run_result(result, knot_id="gate")

        assert signal is not None
        assert signal.token.run_id == result.run_id
        assert signal.reason == "awaiting_human"

    async def test_none_when_the_knot_did_not_suspend(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        with Tapestry(history=history, data_store=data_store) as tapestry:
            response = Parameter(name="response", type_=AgentResponse)
            SuspendingApprovalCheck(
                response=response, auto_approve=True, _config=KnotConfig(id="gate")
            )
        result = await tapestry.run(RunRequest(parameters={"response": _RESPONSE}))
        assert SuspendSignal.from_run_result(result, knot_id="gate") is None


class TestApprovalResumer:
    async def test_resumes_past_the_gate_with_the_decision_bound(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        suspended = _build_suspending_tapestry(history, data_store)
        turn = await suspended.run(RunRequest(parameters={"response": _RESPONSE}))
        signal = SuspendSignal.from_run_result(turn, knot_id="gate")
        assert signal is not None

        # The extended graph: same "response" Parameter and "gate" knot (so
        # they replay), plus a genuinely new "finalize" knot that depends on
        # "response" and the not-yet-existing decision Parameter directly —
        # not on "gate", whose Skipped output would otherwise propagate.
        with Tapestry(history=history, data_store=data_store) as extended:
            response = Parameter(name="response", type_=AgentResponse)
            SuspendingApprovalCheck(response=response, _config=KnotConfig(id="gate"))
            decision_param = Parameter(name="human_decision", type_=HumanDecision)
            Finalize(
                response=response,
                decision=decision_param,
                _config=KnotConfig(id="finalize"),
            )

        resumer = ApprovalResumer(
            graph_tapestry=extended,
            history=history,
            data_store=data_store,
            token=signal.token,
            decision=HumanDecision(approved=True, decided_by="ops-lead"),
            response_knot_id="gate",
            _config=KnotConfig(id="resumer"),
        )
        with Tapestry(history=history, data_store=data_store):
            resumed = await resumer.process(
                graph_tapestry=extended,
                history=history,
                data_store=data_store,
                token=signal.token,
                decision=HumanDecision(approved=True, decided_by="ops-lead"),
                response_knot_id="gate",
            )

        assert resumed.succeeded
        assert resumed.parent_run_id == turn.run_id
        assert resumed.parent_knot_id is None
        assert resumed.outputs["finalize"] == "approved:delete the production database"
        assert resumed.actor == "ops-lead"

    async def test_rejects_a_second_resume_of_the_same_token(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        suspended = _build_suspending_tapestry(history, data_store)
        turn = await suspended.run(RunRequest(parameters={"response": _RESPONSE}))
        signal = SuspendSignal.from_run_result(turn, knot_id="gate")
        assert signal is not None

        with Tapestry(history=history, data_store=data_store) as extended:
            response = Parameter(name="response", type_=AgentResponse)
            SuspendingApprovalCheck(response=response, _config=KnotConfig(id="gate"))
            decision_param = Parameter(name="human_decision", type_=HumanDecision)
            Finalize(response=response, decision=decision_param, _config=KnotConfig(id="finalize"))

        resumer = ApprovalResumer(
            graph_tapestry=extended,
            history=history,
            data_store=data_store,
            token=signal.token,
            decision=HumanDecision(approved=True),
            response_knot_id="gate",
            _config=KnotConfig(id="resumer"),
        )
        await resumer.process(
            graph_tapestry=extended,
            history=history,
            data_store=data_store,
            token=signal.token,
            decision=HumanDecision(approved=True),
            response_knot_id="gate",
        )

        with pytest.raises(ValueError, match="already been resumed"):
            await resumer.process(
                graph_tapestry=extended,
                history=history,
                data_store=data_store,
                token=signal.token,
                decision=HumanDecision(approved=False),
                response_knot_id="gate",
            )

    async def test_rejects_a_stale_output_hash(self) -> None:
        history = InMemoryHistory()
        data_store = InMemoryDataStore()
        suspended = _build_suspending_tapestry(history, data_store)
        turn = await suspended.run(RunRequest(parameters={"response": _RESPONSE}))

        stale_token = ResumeToken(run_id=turn.run_id, output_hash="sha256:not-the-real-hash")

        with Tapestry(history=history, data_store=data_store) as extended:
            response = Parameter(name="response", type_=AgentResponse)
            SuspendingApprovalCheck(response=response, _config=KnotConfig(id="gate"))
            decision_param = Parameter(name="human_decision", type_=HumanDecision)
            Finalize(response=response, decision=decision_param, _config=KnotConfig(id="finalize"))

        resumer = ApprovalResumer(
            graph_tapestry=extended,
            history=history,
            data_store=data_store,
            token=stale_token,
            decision=HumanDecision(approved=True),
            response_knot_id="gate",
            _config=KnotConfig(id="resumer"),
        )
        with pytest.raises(ValueError, match="stale resume token"):
            await resumer.process(
                graph_tapestry=extended,
                history=history,
                data_store=data_store,
                token=stale_token,
                decision=HumanDecision(approved=True),
                response_knot_id="gate",
            )


class TestHumanDecisionIdentityResolver:
    def test_resolves_to_the_decider(self) -> None:
        resolver = HumanDecisionIdentityResolver(HumanDecision(approved=True, decided_by="alex"))
        assert resolver.resolve() == "alex"

    def test_resolves_to_none_when_undecided_by_is_unset(self) -> None:
        resolver = HumanDecisionIdentityResolver(HumanDecision(approved=True))
        assert resolver.resolve() is None

    def test_rejects_non_decision(self) -> None:
        with pytest.raises(TypeError):
            HumanDecisionIdentityResolver("not a decision")  # type: ignore[arg-type]
