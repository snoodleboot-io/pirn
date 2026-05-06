"""Unit tests for :class:`HL7v2MessageParser`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.hl7v2_message_parser import (
    HL7v2MessageParser,
)
from pirn.domains.health.types.clinical_record import ClinicalRecord

_CFG = KnotConfig(id="p")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_string(self) -> None:
        knot = HL7v2MessageParser(message="MSH|...", _config=_CFG)
        with self.assertRaisesRegex(TypeError, "message"):
            await knot.process(message=42)  # type: ignore[arg-type]

    async def test_rejects_empty(self) -> None:
        knot = HL7v2MessageParser(message="MSH|...", _config=_CFG)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(message="")

    async def test_returns_clinical_record(self) -> None:
        knot = HL7v2MessageParser(message="MSH|...", _config=_CFG)
        out = await knot.process(message="MSH|...")
        assert isinstance(out, ClinicalRecord)
        assert out.source_system == "hl7v2"
