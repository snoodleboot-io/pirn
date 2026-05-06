"""Unit tests for :class:`LOINCMapper`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.loinc_mapper import LOINCMapper

_CFG = KnotConfig(id="m")
_KNOT = LOINCMapper(lab_test_names=[], mapping={}, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence_names(self) -> None:
        with self.assertRaisesRegex(TypeError, "lab_test_names"):
            await _KNOT.process(lab_test_names=42, mapping={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping(self) -> None:
        with self.assertRaisesRegex(TypeError, "mapping"):
            await _KNOT.process(lab_test_names=[], mapping=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_name(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            await _KNOT.process(lab_test_names=[1], mapping={})  # type: ignore[list-item]

    async def test_returns_mapped_codes(self) -> None:
        out = await _KNOT.process(lab_test_names=["glucose"], mapping={"glucose": "2345-7"})
        assert isinstance(out, tuple)
        assert out == ("2345-7",)
