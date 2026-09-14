"""Mirrored tests for failover value types (PIR-496 / S2).

Covers :class:`FailoverCandidate` validation and the audit-dict projections of
the trace value objects. ``FailoverAttempt`` now carries a core
:class:`~pirn.core.result.Result` (Ok/Err/Skipped) — the parallel ``FailoverOutcome`` enum is deleted (ADR agents-speaks-core WS5a,
PIR-872);
these tests build the ``Result`` directly.
"""

from __future__ import annotations

import pytest
from pirn.core.err import Err
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_result import FailoverResult


async def _noop() -> None:
    return None


class TestCandidateValidation:
    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValueError, match="name"):
            FailoverCandidate("", _noop)

    def test_rejects_non_callable_operation(self) -> None:
        with pytest.raises(TypeError, match="operation"):
            FailoverCandidate("a", object())  # type: ignore[arg-type]

    def test_rejects_bad_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            FailoverCandidate("a", _noop, timeout=0)

    def test_audit_dict_omits_operation(self) -> None:
        assert FailoverCandidate("a", _noop, timeout=1.5)._pirn_audit_dict() == {
            "name": "a",
            "timeout": 1.5,
        }


class TestTraceProjection:
    def test_attempt_audit_dict_for_a_timeout(self) -> None:
        record = ExceptionRecord.for_knot("a", TimeoutError("timeout"))
        attempt = FailoverAttempt("a", Err(record=record))
        assert attempt._pirn_audit_dict() == {
            "name": "a",
            "outcome": "err",
            "error_type": "TimeoutError",
            "error": "timeout",
        }

    def test_attempt_audit_dict_for_a_plain_error(self) -> None:
        record = ExceptionRecord.for_knot("a", RuntimeError("boom"))
        attempt = FailoverAttempt("a", Err(record=record))
        assert attempt._pirn_audit_dict() == {
            "name": "a",
            "outcome": "err",
            "error_type": "RuntimeError",
            "error": "boom",
        }

    def test_attempt_audit_dict_for_a_circuit_open_skip(self) -> None:
        attempt = FailoverAttempt("a", Skipped(reason=FailoverAttempt.circuit_open_reason))
        assert attempt._pirn_audit_dict() == {
            "name": "a",
            "outcome": "skipped",
            "error_type": None,
            "error": "circuit_open",
        }

    def test_result_audit_dict_projects_attempts(self) -> None:
        result = FailoverResult(
            succeeded=True,
            chosen="a",
            value="v",
            attempts=(FailoverAttempt("a", Ok(value="v")),),
        )
        audit = result._pirn_audit_dict()
        assert audit["succeeded"] is True
        assert audit["chosen"] == "a"
        assert audit["attempts"] == [
            {"name": "a", "outcome": "ok", "error_type": None, "error": None}
        ]
