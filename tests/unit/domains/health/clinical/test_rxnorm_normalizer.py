"""Unit tests for :class:`RxNormNormalizer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical.rxnorm_normalizer import RxNormNormalizer


_CFG = KnotConfig(id="n")
_KNOT = RxNormNormalizer(drug_names=[], mapping={}, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "drug_names"):
            await _KNOT.process(drug_names=42, mapping={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping(self) -> None:
        with self.assertRaisesRegex(TypeError, "mapping"):
            await _KNOT.process(drug_names=[], mapping=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_name(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            await _KNOT.process(drug_names=[1], mapping={})  # type: ignore[list-item]

    async def test_maps_drug_names_to_rxcuis(self) -> None:
        out = await _KNOT.process(drug_names=["aspirin"], mapping={"aspirin": "1191"})
        assert isinstance(out, tuple)
        assert out == ("1191",)
