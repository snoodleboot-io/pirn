"""Mirrored tests for F28-S3 batch progress and its F14 RunState projection."""

from __future__ import annotations

import pytest

from pirn_agents.batch.batch_progress import BatchProgress
from pirn_agents.sessions.run_state import RunState


class TestBatchProgress:
    def test_with_completed_is_immutable(self) -> None:
        base = BatchProgress(batch_id="b1")
        added = base.with_completed("k1")
        assert base.completed_keys == frozenset()
        assert added.completed_keys == frozenset({"k1"})

    def test_with_all_unions_keys(self) -> None:
        progress = BatchProgress(batch_id="b1").with_all(["k1", "k2"]).with_all(["k2", "k3"])
        assert progress.completed_keys == frozenset({"k1", "k2", "k3"})

    def test_is_complete_and_count(self) -> None:
        progress = BatchProgress(batch_id="b1").with_completed("k1")
        assert progress.is_complete("k1") is True
        assert progress.is_complete("k2") is False
        assert progress.completed_count == 1

    def test_round_trips_payload(self) -> None:
        progress = BatchProgress(batch_id="b1", completed_keys=frozenset({"a", "b"}), total=5)
        assert BatchProgress.from_payload(progress.to_payload()) == progress

    def test_rejects_empty_batch_id(self) -> None:
        with pytest.raises(TypeError):
            BatchProgress(batch_id="")

    def test_from_payload_rejects_non_mapping(self) -> None:
        with pytest.raises(TypeError):
            BatchProgress.from_payload(["nope"])


class TestF14RunStateProjection:
    def test_to_run_state_carries_completed_keys_on_cursor(self) -> None:
        progress = BatchProgress(batch_id="b1", completed_keys=frozenset({"k2", "k1"}))
        state = progress.to_run_state()
        assert isinstance(state, RunState)
        assert state.session_id == "b1"
        assert state.cursor.completed_steps == ("k1", "k2")
        assert state.cursor.step_index == 2

    def test_round_trips_through_run_state(self) -> None:
        progress = BatchProgress(batch_id="b1", completed_keys=frozenset({"k1", "k2"}))
        restored = BatchProgress.from_run_state(progress.to_run_state())
        assert restored.batch_id == progress.batch_id
        assert restored.completed_keys == progress.completed_keys

    def test_from_run_state_rejects_non_state(self) -> None:
        with pytest.raises(TypeError):
            BatchProgress.from_run_state("not-a-state")  # type: ignore[arg-type]
