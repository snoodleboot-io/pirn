"""Unit tests for :class:`ICD10CodeValidator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.icd10_code_validator import (
    ICD10CodeValidator,
)


_CFG = KnotConfig(id="v")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence(self) -> None:
        knot = ICD10CodeValidator(codes=[], _config=_CFG)
        with self.assertRaisesRegex(TypeError, "codes"):
            await knot.process(codes=42)  # type: ignore[arg-type]

    async def test_rejects_non_string(self) -> None:
        knot = ICD10CodeValidator(codes=[], _config=_CFG)
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(codes=[1])  # type: ignore[list-item]

    async def test_valid_codes_returns_true(self) -> None:
        knot = ICD10CodeValidator(codes=["E11.9", "I10"], _config=_CFG)
        out = await knot.process(codes=["E11.9", "I10"])
        assert isinstance(out, bool)
        assert out is True

    async def test_invalid_codes_returns_false(self) -> None:
        knot = ICD10CodeValidator(codes=["totally invalid"], _config=_CFG)
        out = await knot.process(codes=["totally invalid"])
        assert out is False
