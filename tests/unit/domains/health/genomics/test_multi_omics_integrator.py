"""Unit tests for :class:`MultiOmicsIntegrator`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.multi_omics_integrator import (
    MultiOmicsIntegrator,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_mapping_rna(self) -> None:
        with pytest.raises(TypeError, match="rna_features"):
            MultiOmicsIntegrator(
                rna_features=42,  # type: ignore[arg-type]
                dna_features={},
                epi_features={},
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_mapping_dna(self) -> None:
        with pytest.raises(TypeError, match="dna_features"):
            MultiOmicsIntegrator(
                rna_features={},
                dna_features=42,  # type: ignore[arg-type]
                epi_features={},
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_mapping_epi(self) -> None:
        with pytest.raises(TypeError, match="epi_features"):
            MultiOmicsIntegrator(
                rna_features={},
                dna_features={},
                epi_features=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="i"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_per_sample_mapping(self) -> None:
        with Tapestry() as t:
            MultiOmicsIntegrator(
                rna_features={"S1": {"g": 1.0}},
                dna_features={"S1": {"v": 1.0}},
                epi_features={"S1": {"e": 1.0}},
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, Mapping)
        assert "S1" in out
