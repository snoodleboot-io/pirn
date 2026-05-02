"""Unit tests for :class:`MEGRawIngestor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.meg_raw_ingestor import MEGRawIngestor
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_path(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            MEGRawIngestor(
                recording_path="",
                signal_id="sig",
                channel_count=128,
                sample_rate_hz=1000.0,
                samples_per_channel=1024,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_positive_channel(self) -> None:
        with pytest.raises(ValueError, match="channel_count"):
            MEGRawIngestor(
                recording_path="x",
                signal_id="sig",
                channel_count=0,
                sample_rate_hz=1000.0,
                samples_per_channel=1024,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_positive_rate(self) -> None:
        with pytest.raises(ValueError, match="sample_rate_hz"):
            MEGRawIngestor(
                recording_path="x",
                signal_id="sig",
                channel_count=128,
                sample_rate_hz=0.0,
                samples_per_channel=1024,
                _config=KnotConfig(id="i"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_signal_frame(self) -> None:
        with Tapestry() as t:
            MEGRawIngestor(
                recording_path="x.fif",
                signal_id="sig",
                channel_count=128,
                sample_rate_hz=1000.0,
                samples_per_channel=1024,
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "sig"
