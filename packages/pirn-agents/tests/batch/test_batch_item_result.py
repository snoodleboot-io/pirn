"""Mirrored tests for the F28-S1 batch item result value + status enum."""

from __future__ import annotations

import pytest

from pirn_agents.batch.batch_item_result import BatchItemResult
from pirn_agents.batch.batch_item_status import BatchItemStatus


def _ok() -> BatchItemResult:
    return BatchItemResult(
        index=2, key="k2", status=BatchItemStatus.OK, output={"n": 1}, attempts=1, latency=0.5
    )


class TestBatchItemResultRoundTrip:
    def test_round_trips_without_data_loss(self) -> None:
        restored = BatchItemResult.from_payload(_ok().to_payload())
        assert restored == _ok()

    def test_payload_covers_all_fields(self) -> None:
        payload = _ok().to_payload()
        assert set(payload) == {"index", "key", "status", "output", "error", "attempts", "latency"}

    def test_status_serialises_to_stable_token(self) -> None:
        assert _ok().to_payload()["status"] == "ok"

    def test_non_primitive_output_is_stringified(self) -> None:
        result = BatchItemResult(index=0, key="k", status=BatchItemStatus.OK, output=object())
        assert isinstance(result.to_payload()["output"], str)

    def test_nested_output_is_json_safe(self) -> None:
        result = BatchItemResult(
            index=0, key="k", status=BatchItemStatus.OK, output={"a": [1, {"b": 2}]}
        )
        assert result.to_payload()["output"] == {"a": [1, {"b": 2}]}


class TestBatchItemResultValidation:
    def test_succeeded_reflects_status(self) -> None:
        assert _ok().succeeded is True
        assert (
            BatchItemResult(index=0, key="k", status=BatchItemStatus.ERROR, error="x").succeeded
            is False
        )

    def test_rejects_negative_index(self) -> None:
        with pytest.raises(ValueError):
            BatchItemResult(index=-1, key="k", status=BatchItemStatus.OK)

    def test_rejects_empty_key(self) -> None:
        with pytest.raises(TypeError):
            BatchItemResult(index=0, key="", status=BatchItemStatus.OK)

    def test_rejects_non_status(self) -> None:
        with pytest.raises(TypeError):
            BatchItemResult(index=0, key="k", status="ok")  # type: ignore[arg-type]

    def test_from_payload_rejects_non_mapping(self) -> None:
        with pytest.raises(TypeError):
            BatchItemResult.from_payload(["not", "a", "mapping"])

    def test_is_opaque_audit_dict(self) -> None:
        assert _ok()._pirn_audit_dict() == _ok().to_payload()
