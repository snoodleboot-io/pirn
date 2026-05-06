"""Unit tests for :class:`MultiOmicsIntegrator`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.multi_omics_integrator import MultiOmicsIntegrator

_CFG = KnotConfig(id="i")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> MultiOmicsIntegrator:
        return MultiOmicsIntegrator(
            rna_features={"S1": {"g": 1.0}},
            dna_features={"S1": {"v": 1.0}},
            epi_features={"S1": {"e": 1.0}},
            _config=_CFG,
        )

    async def test_rejects_non_mapping_rna(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "rna_features"):
            await knot.process(rna_features=42, dna_features={}, epi_features={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping_dna(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "dna_features"):
            await knot.process(rna_features={}, dna_features=42, epi_features={})  # type: ignore[arg-type]

    async def test_rejects_non_mapping_epi(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "epi_features"):
            await knot.process(rna_features={}, dna_features={}, epi_features=42)  # type: ignore[arg-type]

    async def test_returns_per_sample_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            rna_features={"S1": {"g": 1.0}},
            dna_features={"S1": {"v": 1.0}},
            epi_features={"S1": {"e": 1.0}},
        )
        assert isinstance(out, Mapping)
        assert "S1" in out
