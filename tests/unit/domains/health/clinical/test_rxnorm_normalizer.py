"""Unit tests for :class:`RxNormNormalizer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.rxnorm_normalizer import RxNormNormalizer
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="drug_names"):
            RxNormNormalizer(
                drug_names=42,  # type: ignore[arg-type]
                mapping={},
                _config=KnotConfig(id="n"),
            )

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(TypeError, match="mapping"):
            RxNormNormalizer(
                drug_names=[],
                mapping=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="n"),
            )

    def test_rejects_non_string_name(self) -> None:
        with pytest.raises(TypeError, match="string"):
            RxNormNormalizer(
                drug_names=[1],  # type: ignore[list-item]
                mapping={},
                _config=KnotConfig(id="n"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_maps_drug_names_to_rxcuis(self) -> None:
        with Tapestry() as t:
            RxNormNormalizer(
                drug_names=["aspirin"],
                mapping={"aspirin": "1191"},
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["n"]
        assert isinstance(out, tuple)
        assert out == ("1191",)
