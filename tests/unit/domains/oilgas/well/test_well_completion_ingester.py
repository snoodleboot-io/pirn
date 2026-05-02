"""Unit tests for :class:`WellCompletionIngester`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.drilling_parameters import DrillingParameters
from pirn.domains.oilgas.well.well_completion_ingester import WellCompletionIngester
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_well_id(self) -> None:
        with pytest.raises(ValueError, match="well_id"):
            WellCompletionIngester(
                well_id="",
                record_path="/x",
                _config=KnotConfig(id="wc"),
            )

    def test_rejects_empty_record_path(self) -> None:
        with pytest.raises(ValueError, match="record_path"):
            WellCompletionIngester(
                well_id="W",
                record_path="",
                _config=KnotConfig(id="wc"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_drilling_parameters(self) -> None:
        with Tapestry() as t:
            WellCompletionIngester(
                well_id="W",
                record_path="/x",
                _config=KnotConfig(id="wc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["wc"]
        assert isinstance(out, DrillingParameters)
        assert out.well_id == "W"
