"""Mirrored tests for the S1 run-state / checkpoint model (PIR-354)."""

from __future__ import annotations

import pytest

from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.run_checkpoint import RunCheckpoint
from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_tool_result import SessionToolResult


def _rich_state() -> RunState:
    return RunState(
        session_id="sess-1",
        messages=(
            SessionMessage(role="user", content="hi"),
            SessionMessage(role="assistant", content="hello"),
        ),
        plan=("plan-a", "plan-b", "plan-c"),
        tool_results=(SessionToolResult(call_id="c1", tool_name="search", output={"hits": 2}),),
        cursor=ExecutionCursor(step_index=1, completed_steps=("plan-a",)),
    )


class TestRunStateRoundTrip:
    def test_round_trips_without_data_loss(self) -> None:
        state = _rich_state()
        restored = RunState.from_payload(state.to_payload())
        assert restored == state

    def test_payload_covers_all_fields(self) -> None:
        payload = _rich_state().to_payload()
        assert set(payload) == {"session_id", "messages", "plan", "tool_results", "cursor"}

    def test_remaining_plan_is_uncomputed_tail(self) -> None:
        assert _rich_state().remaining_plan() == ("plan-b", "plan-c")

    def test_with_message_appends_immutably(self) -> None:
        state = _rich_state()
        extended = state.with_message(SessionMessage(role="user", content="more"))
        assert len(state.messages) == 2
        assert extended.messages[-1].content == "more"

    def test_rejects_empty_session_id(self) -> None:
        with pytest.raises(TypeError):
            RunState(session_id="")


class TestExecutionCursor:
    def test_advanced_increments_and_appends(self) -> None:
        cursor = ExecutionCursor().advanced("s1").advanced("s2")
        assert cursor.step_index == 2
        assert cursor.completed_steps == ("s1", "s2")

    def test_rejects_negative_index(self) -> None:
        with pytest.raises(ValueError, match="step_index"):
            ExecutionCursor(step_index=-1)


class TestRunCheckpointContentAddressing:
    def test_create_hashes_state(self) -> None:
        cp = RunCheckpoint.create(_rich_state())
        assert cp.checkpoint_id == RunCheckpoint.content_hash(_rich_state())

    def test_identical_states_dedup_to_same_id(self) -> None:
        assert (
            RunCheckpoint.create(_rich_state()).checkpoint_id
            == RunCheckpoint.create(_rich_state()).checkpoint_id
        )

    def test_different_states_have_different_ids(self) -> None:
        other = RunState.from_payload(_rich_state().to_payload())
        changed = other.with_message(SessionMessage(role="user", content="x"))
        assert (
            RunCheckpoint.create(_rich_state()).checkpoint_id
            != RunCheckpoint.create(changed).checkpoint_id
        )

    def test_checkpoint_round_trips(self) -> None:
        cp = RunCheckpoint.create(_rich_state())
        assert RunCheckpoint.from_payload(cp.to_payload()) == cp

    def test_create_rejects_non_state(self) -> None:
        with pytest.raises(TypeError):
            RunCheckpoint.create("bad")  # type: ignore[arg-type]
