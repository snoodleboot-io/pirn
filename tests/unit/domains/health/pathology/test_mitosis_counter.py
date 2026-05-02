"""Unit tests for :class:`MitosisCounter`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.pathology.mitosis_counter import MitosisCounter
from pirn.domains.health.types.wsi_tile import WSITile
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="tiles"):
            MitosisCounter(
                tiles=42,  # type: ignore[arg-type]
                confidence_threshold=0.5,
                _config=KnotConfig(id="m"),
            )

    def test_rejects_non_tile(self) -> None:
        with pytest.raises(TypeError, match="WSITile"):
            MitosisCounter(
                tiles=["x"],  # type: ignore[list-item]
                confidence_threshold=0.5,
                _config=KnotConfig(id="m"),
            )

    def test_rejects_non_numeric_threshold(self) -> None:
        with pytest.raises(TypeError, match="numeric"):
            MitosisCounter(
                tiles=(),
                confidence_threshold="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="m"),
            )

    def test_rejects_out_of_range_threshold(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            MitosisCounter(
                tiles=(),
                confidence_threshold=1.5,
                _config=KnotConfig(id="m"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_int(self) -> None:
        with Tapestry() as t:
            MitosisCounter(
                tiles=(WSITile(),),
                confidence_threshold=0.5,
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, int)
