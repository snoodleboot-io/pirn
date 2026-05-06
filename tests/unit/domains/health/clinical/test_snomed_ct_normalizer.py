"""Unit tests for :class:`SnomedCTNormalizer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.snomed_ct_normalizer import (
    SnomedCTNormalizer,
)


_CFG = KnotConfig(id="n")
_KNOT = SnomedCTNormalizer(codes=[], mapping={}, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "codes"):
            await _KNOT.process(codes=42, mapping={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping(self) -> None:
        with self.assertRaisesRegex(TypeError, "mapping"):
            await _KNOT.process(codes=[], mapping=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_code(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            await _KNOT.process(codes=[1], mapping={})  # type: ignore[list-item]

    async def test_maps_codes_to_snomed(self) -> None:
        out = await _KNOT.process(codes=["E11.9"], mapping={"E11.9": "44054006"})
        assert isinstance(out, tuple)
        assert out == ("44054006",)
