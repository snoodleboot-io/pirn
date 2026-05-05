"""Unit tests for :class:`DiagnosisCodeRollup`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.diagnosis_code_rollup import (
    DiagnosisCodeRollup,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence_codes(self) -> None:
        with self.assertRaisesRegex(TypeError, "codes"):
            DiagnosisCodeRollup(
                codes=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_string_code(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            DiagnosisCodeRollup(
                codes=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_int_prefix_length(self) -> None:
        with self.assertRaisesRegex(TypeError, "prefix_length"):
            DiagnosisCodeRollup(
                codes=[],
                prefix_length="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="r"),
            )

    def test_rejects_non_positive_prefix_length(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            DiagnosisCodeRollup(
                codes=[],
                prefix_length=0,
                _config=KnotConfig(id="r"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rolls_up_to_prefix(self) -> None:
        with Tapestry() as t:
            DiagnosisCodeRollup(
                codes=["E11.9", "I10"],
                prefix_length=3,
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, tuple)
        assert out == ("E11", "I10")
