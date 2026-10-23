"""Unit tests for :class:`EvalCaseResult` as ``Payload[EvalCaseFrame, Mapping[str, float]]`` (PIR-874)."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_agents.evaluation.eval_case_frame import EvalCaseFrame
from pirn_agents.evaluation.eval_case_result import EvalCaseResult


def _result(**overrides: object) -> EvalCaseResult:
    kwargs: dict[str, object] = {
        "item_id": "i1",
        "metrics": {"exact_match": 1.0},
        "passed": True,
        "detail": {"output": "x"},
    }
    kwargs.update(overrides)
    return EvalCaseResult(**kwargs)  # type: ignore[arg-type]


class TestEvalCaseResult:
    def test_is_a_payload_with_frame_and_data(self) -> None:
        result = _result()

        assert isinstance(result, Payload)
        assert isinstance(result.metadata, EvalCaseFrame)
        assert result.metadata.item_id == "i1"
        assert result.metadata.passed is True
        assert result.metadata.detail == {"output": "x"}
        assert result.data == {"exact_match": 1.0}

    def test_defaults(self) -> None:
        result = EvalCaseResult(item_id="i", metrics={})

        assert result.metadata.passed is None
        assert result.metadata.detail == {}

    def test_audit_dict_has_both_halves(self) -> None:
        audit = _result()._pirn_audit_dict()

        assert audit["item_id"] == "i1"
        assert audit["passed"] is True
        assert audit["detail"] == {"output": "x"}
        assert audit["metrics"] == {"exact_match": 1.0}

    def test_equality_is_structural(self) -> None:
        assert _result() == _result()
        assert _result() != _result(metrics={"exact_match": 0.0})
        assert _result() != _result(passed=False)
