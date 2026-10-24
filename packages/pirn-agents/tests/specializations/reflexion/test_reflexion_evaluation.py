"""Unit tests for :class:`ReflexionEvaluation` as ``Payload[ReflexionEvaluationFrame, str]`` (PIR-874)."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_agents.specializations.reflexion.reflexion_evaluation import ReflexionEvaluation
from pirn_agents.specializations.reflexion.reflexion_evaluation_frame import (
    ReflexionEvaluationFrame,
)


class TestReflexionEvaluation:
    def test_is_a_payload_with_frame_and_data(self) -> None:
        evaluation = ReflexionEvaluation(success=False, feedback="too short")

        assert isinstance(evaluation, Payload)
        assert isinstance(evaluation.metadata, ReflexionEvaluationFrame)
        assert evaluation.metadata.success is False
        assert evaluation.data == "too short"

    def test_feedback_defaults_to_empty(self) -> None:
        assert ReflexionEvaluation(success=True).data == ""

    def test_audit_dict_has_both_halves(self) -> None:
        audit = ReflexionEvaluation(success=False, feedback="too short")._pirn_audit_dict()

        assert audit["success"] is False
        assert audit["feedback"] == "too short"

    def test_equality_is_structural(self) -> None:
        assert ReflexionEvaluation(True, "a") == ReflexionEvaluation(True, "a")
        assert ReflexionEvaluation(True, "a") != ReflexionEvaluation(False, "a")
        assert ReflexionEvaluation(True, "a") != ReflexionEvaluation(True, "b")
