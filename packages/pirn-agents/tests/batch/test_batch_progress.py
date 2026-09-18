"""Mirrored tests for the per-fire batch summary value."""

from __future__ import annotations

import pytest

from pirn_agents.batch.batch_progress import BatchProgress


class TestBatchProgress:
    def test_completed_count_and_membership(self) -> None:
        progress = BatchProgress(batch_id="b1", completed_keys=frozenset({"k1", "k2"}), total=3)
        assert progress.completed_count == 2
        assert progress.is_complete("k1") is True
        assert progress.is_complete("k3") is False

    def test_payload_is_sorted_and_json_friendly(self) -> None:
        progress = BatchProgress(batch_id="b1", completed_keys=frozenset({"b", "a"}), total=5)
        assert progress.to_payload() == {"batch_id": "b1", "completed_keys": ["a", "b"], "total": 5}
        assert progress._pirn_audit_dict() == progress.to_payload()

    def test_rejects_empty_batch_id(self) -> None:
        with pytest.raises(TypeError):
            BatchProgress(batch_id="")

    def test_rejects_non_frozenset_keys(self) -> None:
        with pytest.raises(TypeError):
            BatchProgress(batch_id="b1", completed_keys={"a"})

    def test_checkpoints_nothing(self) -> None:
        """A summary only: no restore path back into a run (PIR-872)."""
        for name in (
            "to_run_state",
            "from_run_state",
            "from_payload",
            "with_completed",
            "with_all",
        ):
            assert not hasattr(BatchProgress, name), name
