"""Unit tests for :class:`SnomedCTNormalizer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.snomed_ct_normalizer import (
    SnomedCTNormalizer,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="codes"):
            SnomedCTNormalizer(
                codes=42,  # type: ignore[arg-type]
                mapping={},
                _config=KnotConfig(id="n"),
            )

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(TypeError, match="mapping"):
            SnomedCTNormalizer(
                codes=[],
                mapping=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="n"),
            )

    def test_rejects_non_string_code(self) -> None:
        with pytest.raises(TypeError, match="string"):
            SnomedCTNormalizer(
                codes=[1],  # type: ignore[list-item]
                mapping={},
                _config=KnotConfig(id="n"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_maps_codes_to_snomed(self) -> None:
        with Tapestry() as t:
            SnomedCTNormalizer(
                codes=["E11.9"],
                mapping={"E11.9": "44054006"},
                _config=KnotConfig(id="n"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["n"]
        assert isinstance(out, tuple)
        assert out == ("44054006",)
