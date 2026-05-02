"""Unit tests for :class:`LOINCMapper`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.clinical.loinc_mapper import LOINCMapper
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence_names(self) -> None:
        with pytest.raises(TypeError, match="lab_test_names"):
            LOINCMapper(
                lab_test_names=42,  # type: ignore[arg-type]
                mapping={},
                _config=KnotConfig(id="m"),
            )

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(TypeError, match="mapping"):
            LOINCMapper(
                lab_test_names=[],
                mapping=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="m"),
            )

    def test_rejects_non_string_name(self) -> None:
        with pytest.raises(TypeError, match="string"):
            LOINCMapper(
                lab_test_names=[1],  # type: ignore[list-item]
                mapping={},
                _config=KnotConfig(id="m"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_mapped_codes(self) -> None:
        with Tapestry() as t:
            LOINCMapper(
                lab_test_names=["glucose"],
                mapping={"glucose": "2345-7"},
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, tuple)
        assert out == ("2345-7",)
