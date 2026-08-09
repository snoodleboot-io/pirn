"""Mirrored tests for the F28-S1 batch item result value + status enum."""

from __future__ import annotations

import pytest
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.batch.batch_item_result import BatchItemResult
from pirn_agents.batch.batch_item_status import BatchItemStatus


def _ok() -> BatchItemResult:
    return BatchItemResult(
        index=2, key="k2", status=BatchItemStatus.OK, output={"n": 1}, attempts=1, latency=0.5
    )


def _record(message: str = "boom") -> ExceptionRecord:
    return ExceptionRecord(
        run_id="<unbound>",
        knot_id="k9",
        exc_type="RuntimeError",
        message=message,
        traceback_text="Traceback (most recent call last):\n  RuntimeError: boom\n",
    )


def _failed(record: ExceptionRecord | None = None) -> BatchItemResult:
    return BatchItemResult(
        index=9,
        key="k9",
        status=BatchItemStatus.ERROR,
        exception=record if record is not None else _record(),
        attempts=3,
        latency=1.25,
    )


class TestBatchItemResultRoundTrip:
    def test_round_trips_without_data_loss(self) -> None:
        restored = BatchItemResult.from_payload(_ok().to_payload())
        assert restored == _ok()

    def test_payload_covers_all_fields(self) -> None:
        payload = _ok().to_payload()
        assert set(payload) == {
            "index",
            "key",
            "status",
            "output",
            "error",
            "exception",
            "attempts",
            "latency",
        }

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


class TestBatchItemResultExceptionRecord:
    def test_failure_carries_the_full_record(self) -> None:
        record = _record()
        assert _failed(record).exception is record

    def test_error_is_derived_from_the_record_message(self) -> None:
        assert _failed().error == "boom"

    def test_error_is_none_without_a_record(self) -> None:
        assert _ok().error is None

    def test_error_is_read_only(self) -> None:
        with pytest.raises(AttributeError):
            _failed().error = "clobbered"  # type: ignore[misc]

    def test_payload_carries_the_whole_record(self) -> None:
        payload = _failed().to_payload()
        assert payload["exception"]["exc_type"] == "RuntimeError"
        assert payload["exception"]["traceback_text"].startswith("Traceback")
        assert payload["error"] == "boom"

    def test_round_trips_a_record_without_data_loss(self) -> None:
        # Equality covers the record's ``id`` and ``occurred_at`` too, so this
        # pins that the checkpoint keeps a failure's full identity.
        failed = _failed()
        assert BatchItemResult.from_payload(failed.to_payload()) == failed

    def test_rejects_non_record_exception(self) -> None:
        with pytest.raises(TypeError):
            BatchItemResult(
                index=0,
                key="k",
                status=BatchItemStatus.ERROR,
                exception="boom",  # type: ignore[arg-type]
            )


class TestBatchItemResultLegacyPayload:
    """Checkpoints written before the record existed carry a bare ``error`` str."""

    @staticmethod
    def _legacy() -> dict[str, object]:
        return {
            "index": 4,
            "key": "k4",
            "status": "error",
            "output": None,
            "error": "legacy failure detail",
            "attempts": 2,
            "latency": 0.75,
        }

    def test_legacy_payload_still_loads(self) -> None:
        restored = BatchItemResult.from_payload(self._legacy())
        assert restored.index == 4
        assert restored.key == "k4"
        assert restored.status is BatchItemStatus.ERROR
        assert restored.attempts == 2
        assert restored.latency == 0.75

    def test_legacy_error_string_is_preserved(self) -> None:
        assert BatchItemResult.from_payload(self._legacy()).error == "legacy failure detail"

    def test_legacy_error_string_is_lifted_into_a_record(self) -> None:
        record = BatchItemResult.from_payload(self._legacy()).exception
        assert record is not None
        assert record.message == "legacy failure detail"
        assert record.knot_id == "k4"
        assert record.traceback_text == ""

    def test_legacy_payload_without_error_has_no_record(self) -> None:
        payload = self._legacy() | {"status": "ok", "error": None}
        assert BatchItemResult.from_payload(payload).exception is None


class TestBatchItemResultValidation:
    def test_succeeded_reflects_status(self) -> None:
        assert _ok().succeeded is True
        assert _failed().succeeded is False

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
