"""Unit tests for :class:`JudgeVerdict` as ``Payload[JudgeVerdictFrame, str]`` (PIR-874)."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_agents.specializations.evaluator_optimizer.judge_verdict import JudgeVerdict
from pirn_agents.specializations.evaluator_optimizer.judge_verdict_frame import JudgeVerdictFrame


class TestJudgeVerdict:
    def test_is_a_payload_with_frame_and_data(self) -> None:
        verdict = JudgeVerdict(score=7.5, feedback="add detail")

        assert isinstance(verdict, Payload)
        assert isinstance(verdict.metadata, JudgeVerdictFrame)
        assert verdict.metadata.score == 7.5
        assert verdict.data == "add detail"

    def test_feedback_defaults_to_empty(self) -> None:
        assert JudgeVerdict(score=1.0).data == ""

    def test_audit_dict_has_both_halves(self) -> None:
        audit = JudgeVerdict(score=7.5, feedback="add detail")._pirn_audit_dict()

        assert audit["score"] == 7.5
        assert audit["feedback"] == "add detail"

    def test_equality_is_structural(self) -> None:
        assert JudgeVerdict(score=2.0, feedback="x") == JudgeVerdict(score=2.0, feedback="x")
        assert JudgeVerdict(score=2.0, feedback="x") != JudgeVerdict(score=3.0, feedback="x")
        assert JudgeVerdict(score=2.0, feedback="x") != JudgeVerdict(score=2.0, feedback="y")
