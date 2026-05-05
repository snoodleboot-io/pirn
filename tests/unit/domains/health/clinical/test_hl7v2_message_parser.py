"""Unit tests for :class:`HL7v2MessageParser`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.hl7v2_message_parser import (
    HL7v2MessageParser,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_string(self) -> None:
        with self.assertRaisesRegex(TypeError, "message"):
            HL7v2MessageParser(
                message=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="p"),
            )

    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            HL7v2MessageParser(
                message="",
                _config=KnotConfig(id="p"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_clinical_record(self) -> None:
        with Tapestry() as t:
            HL7v2MessageParser(
                message="MSH|...",
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, ClinicalRecord)
        assert out.source_system == "hl7v2"
