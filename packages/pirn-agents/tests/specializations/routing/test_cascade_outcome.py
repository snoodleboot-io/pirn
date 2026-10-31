"""``CascadeOutcome`` is ``Payload[CascadeFrame, Any]`` (PIR-868, PIR-874)."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_agents.specializations.routing.cascade_frame import CascadeFrame
from pirn_agents.specializations.routing.cascade_outcome import CascadeOutcome


def _outcome(value: object = "A", chosen: str | None = "cheap") -> CascadeOutcome:
    return CascadeOutcome(
        value=value,
        chosen=chosen,
        succeeded=True,
        escalated=False,
        attempted=("cheap",),
        decisions=("cheap: accepted (confidence=1.0)",),
        confidence=1.0,
    )


class TestCascadeOutcome:
    def test_is_a_payload_with_a_cascade_frame(self) -> None:
        outcome = _outcome()
        assert isinstance(outcome, Payload)
        assert isinstance(outcome.metadata, CascadeFrame)

    def test_metadata_and_data_halves(self) -> None:
        outcome = _outcome()
        assert outcome.data == "A"
        assert outcome.metadata.chosen == "cheap"
        assert outcome.metadata.succeeded is True
        assert outcome.metadata.escalated is False
        assert outcome.metadata.attempted == ("cheap",)
        assert outcome.metadata.decisions == ("cheap: accepted (confidence=1.0)",)
        assert outcome.metadata.confidence == 1.0

    def test_confidence_defaults_to_none(self) -> None:
        outcome = CascadeOutcome(
            value=None,
            chosen=None,
            succeeded=False,
            escalated=True,
            attempted=(),
            decisions=(),
        )
        assert outcome.metadata.confidence is None

    def test_audit_dict_includes_both_halves(self) -> None:
        audit = _outcome()._pirn_audit_dict()
        assert audit["value"] == "'A'"
        assert audit["chosen"] == "cheap"
        assert audit["attempted"] == ["cheap"]
        assert audit["decisions"] == ["cheap: accepted (confidence=1.0)"]
        assert audit["confidence"] == 1.0

    def test_equal_by_value(self) -> None:
        assert _outcome() == _outcome()

    def test_unequal_when_data_or_metadata_differs(self) -> None:
        assert _outcome("A") != _outcome("B")
        assert _outcome(chosen="cheap") != _outcome(chosen="strong")
