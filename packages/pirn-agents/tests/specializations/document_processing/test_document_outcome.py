"""Unit tests for :class:`DocumentOutcome` (``Payload[DocumentOutcomeFrame, str]``, PIR-874)."""

from __future__ import annotations

import unittest

from pirn.core.payload import Payload

from pirn_agents.specializations.base.nested_audit_value import NestedAuditValue
from pirn_agents.specializations.document_processing.document_outcome import DocumentOutcome
from pirn_agents.specializations.document_processing.document_outcome_frame import (
    DocumentOutcomeFrame,
)


class TestDocumentOutcome(unittest.TestCase):
    def test_is_payload_with_frame_metadata(self) -> None:
        outcome = DocumentOutcome(source_id="a", embedded=2, unchanged=1, removed=3)
        assert isinstance(outcome, Payload)
        assert isinstance(outcome.metadata, DocumentOutcomeFrame)
        assert (
            outcome.metadata.embedded,
            outcome.metadata.unchanged,
            outcome.metadata.removed,
        ) == (2, 1, 3)
        assert outcome.metadata.error is None

    def test_data_is_source_id(self) -> None:
        assert DocumentOutcome(source_id="doc-1").data == "doc-1"

    def test_defaults(self) -> None:
        outcome = DocumentOutcome(source_id="a", error="boom")
        assert outcome.metadata == DocumentOutcomeFrame(error="boom")

    def test_audit_dict_has_both_halves(self) -> None:
        audit = NestedAuditValue._audit_form(DocumentOutcome(source_id="a", embedded=2, error="x"))
        assert audit["source_id"] == "a"
        assert audit["embedded"] == 2
        assert audit["error"] == "x"

    def test_equality_is_structural(self) -> None:
        assert DocumentOutcome(source_id="a", embedded=1) == DocumentOutcome(
            source_id="a", embedded=1
        )
        assert DocumentOutcome(source_id="a", embedded=1) != DocumentOutcome(
            source_id="a", embedded=2
        )
        assert DocumentOutcome(source_id="a") != DocumentOutcome(source_id="b")
