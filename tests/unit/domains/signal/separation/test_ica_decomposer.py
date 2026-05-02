"""Unit tests for :class:`ICADecomposer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.separation.ica_decomposer import ICADecomposer
from pirn.domains.signal.types.source_frame import SourceFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_source_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="source_count"):
                ICADecomposer(
                    signal=sig,
                    source_count=0,
                    _config=KnotConfig(id="ica"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_source_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ICADecomposer(
                signal=sig,
                source_count=3,
                _config=KnotConfig(id="ica"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ica"]
        assert isinstance(out, SourceFrame)
        assert out.source_count == 3
        assert out.mixing_matrix_shape == (1, 3)
