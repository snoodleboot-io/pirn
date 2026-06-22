"""Unit tests for :class:`DiagnosisCodeRollup`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_health.clinical.diagnosis_code_rollup import (
    DiagnosisCodeRollup,
)

_CFG = KnotConfig(id="r")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_codes(self) -> None:
        knot = DiagnosisCodeRollup(codes=[], _config=_CFG)
        with self.assertRaisesRegex(TypeError, "codes"):
            await knot.process(codes=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_code(self) -> None:
        knot = DiagnosisCodeRollup(codes=[], _config=_CFG)
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(codes=[1])  # type: ignore[list-item]

    async def test_rejects_non_int_prefix_length(self) -> None:
        knot = DiagnosisCodeRollup(codes=[], _config=_CFG)
        with self.assertRaisesRegex(TypeError, "prefix_length"):
            await knot.process(codes=[], prefix_length="x")  # type: ignore[arg-type]

    async def test_rejects_non_positive_prefix_length(self) -> None:
        knot = DiagnosisCodeRollup(codes=[], _config=_CFG)
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(codes=[], prefix_length=0)

    async def test_rolls_up_to_prefix(self) -> None:
        knot = DiagnosisCodeRollup(codes=["E11.9", "I10"], prefix_length=3, _config=_CFG)
        out = await knot.process(codes=["E11.9", "I10"], prefix_length=3)
        assert isinstance(out, tuple)
        assert out == ("E11", "I10")
