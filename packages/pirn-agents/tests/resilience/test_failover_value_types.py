"""Mirrored tests for failover value types (PIR-496 / S2).

Covers :class:`FailoverCandidate` validation and the audit-dict projections of
the trace value objects.
"""

from __future__ import annotations

import pytest

from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_candidate import FailoverCandidate
from pirn_agents.resilience.failover_outcome import FailoverOutcome
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
    def test_attempt_audit_dict(self) -> None:
        attempt = FailoverAttempt("a", FailoverOutcome.TIMEOUT, "timeout")
        assert attempt._pirn_audit_dict() == {
            "name": "a",
            "outcome": "timeout",
            "error": "timeout",
        }

    def test_result_audit_dict_projects_attempts(self) -> None:
        result = FailoverResult(
            succeeded=True,
            chosen="a",
            value="v",
            attempts=(FailoverAttempt("a", FailoverOutcome.SUCCESS, None),),
        )
        audit = result._pirn_audit_dict()
        assert audit["succeeded"] is True
        assert audit["chosen"] == "a"
        assert audit["attempts"] == [{"name": "a", "outcome": "success", "error": None}]
