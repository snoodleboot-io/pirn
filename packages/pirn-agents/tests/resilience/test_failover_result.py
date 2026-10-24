"""``FailoverResult`` is ``Payload[FailoverFrame, Any]`` (PIR-868, PIR-874)."""

from __future__ import annotations

from pirn.core.ok import Ok
from pirn.core.payload import Payload

from pirn_agents.resilience.failover_attempt import FailoverAttempt
from pirn_agents.resilience.failover_frame import FailoverFrame
from pirn_agents.resilience.failover_result import FailoverResult


def _result(value: object = "v", chosen: str | None = "a") -> FailoverResult:
    return FailoverResult(
        succeeded=True,
        chosen=chosen,
        value=value,
        attempts=(FailoverAttempt("a", Ok(value="v")),),
    )


class TestFailoverResult:
    def test_is_a_payload_with_a_failover_frame(self) -> None:
        result = _result()
        assert isinstance(result, Payload)
        assert isinstance(result.metadata, FailoverFrame)

    def test_metadata_and_data_halves(self) -> None:
        result = _result()
        assert result.data == "v"
        assert result.metadata.succeeded is True
        assert result.metadata.chosen == "a"
        assert [a.name for a in result.metadata.attempts] == ["a"]

    def test_audit_dict_includes_both_halves(self) -> None:
        audit = _result()._pirn_audit_dict()
        assert audit["succeeded"] is True
        assert audit["chosen"] == "a"
        assert audit["attempts"] == [
            {"name": "a", "outcome": "ok", "error_type": None, "error": None}
        ]
        assert audit["value"] == "'v'"

    def test_equal_by_value(self) -> None:
        assert _result() == _result()

    def test_unequal_when_data_or_metadata_differs(self) -> None:
        assert _result("v") != _result("w")
        assert _result(chosen="a") != _result(chosen="b")
