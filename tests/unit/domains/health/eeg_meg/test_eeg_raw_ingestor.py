"""Unit tests for :class:`EEGRawIngestor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.eeg_raw_ingestor import EEGRawIngestor
from pirn.domains.health.types.raw_eeg import RawEEG
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            EEGRawIngestor(
                recording_path="",
                subject_id="S1",
                channel_count=64,
                sample_rate_hz=1000.0,
                duration_sec=120.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_int_channel(self) -> None:
        with self.assertRaisesRegex(TypeError, "channel_count"):
            EEGRawIngestor(
                recording_path="x",
                subject_id="S1",
                channel_count="x",  # type: ignore[arg-type]
                sample_rate_hz=1000.0,
                duration_sec=120.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_positive_channel(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            EEGRawIngestor(
                recording_path="x",
                subject_id="S1",
                channel_count=0,
                sample_rate_hz=1000.0,
                duration_sec=120.0,
                _config=KnotConfig(id="i"),
            )

    def test_rejects_non_positive_rate(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            EEGRawIngestor(
                recording_path="x",
                subject_id="S1",
                channel_count=64,
                sample_rate_hz=0.0,
                duration_sec=120.0,
                _config=KnotConfig(id="i"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_raw_eeg(self) -> None:
        with Tapestry() as t:
            EEGRawIngestor(
                recording_path="x.edf",
                subject_id="S1",
                channel_count=64,
                sample_rate_hz=1000.0,
                duration_sec=120.0,
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, RawEEG)
        assert out.subject_id == "S1"
