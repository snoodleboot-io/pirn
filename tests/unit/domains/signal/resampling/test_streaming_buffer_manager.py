"""Unit tests for :class:`StreamingBufferManager`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.streaming_buffer_manager import (
    StreamingBufferManager,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_frame_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="frame_size"):
                StreamingBufferManager(
                    signal=sig,
                    frame_size=0,
                    hop_size=128,
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_non_positive_hop_size(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="hop_size"):
                StreamingBufferManager(
                    signal=sig,
                    frame_size=512,
                    hop_size=0,
                    _config=KnotConfig(id="b"),
                )

    def test_rejects_hop_greater_than_frame(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="not exceed"):
                StreamingBufferManager(
                    signal=sig,
                    frame_size=128,
                    hop_size=512,
                    _config=KnotConfig(id="b"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_signal_frame_with_framed_marker(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            StreamingBufferManager(
                signal=sig,
                frame_size=512,
                hop_size=256,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:framed"
