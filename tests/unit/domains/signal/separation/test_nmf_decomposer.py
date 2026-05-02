"""Unit tests for :class:`NMFDecomposer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.separation.nmf_decomposer import NMFDecomposer
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_component_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="component_count"):
                NMFDecomposer(
                    signal=sig,
                    component_count=0,
                    _config=KnotConfig(id="nmf"),
                )

    def test_rejects_non_positive_max_iterations(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="max_iterations"):
                NMFDecomposer(
                    signal=sig,
                    component_count=4,
                    max_iterations=0,
                    _config=KnotConfig(id="nmf"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_source_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            NMFDecomposer(
                signal=sig,
                component_count=4,
                _config=KnotConfig(id="nmf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["nmf"]
        assert isinstance(out, SourceFrame)
        assert out.source_count == 4
