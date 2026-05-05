"""Unit tests for :class:`FrequencyDecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.frequency_decomposer import FrequencyDecomposer
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_frequencies(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                FrequencyDecomposer(
                    volume=volume,
                    center_frequencies_hz=(),
                    _config=KnotConfig(id="fd"),
                )

    def test_rejects_non_positive_frequency(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                FrequencyDecomposer(
                    volume=volume,
                    center_frequencies_hz=(10.0, -5.0),
                    _config=KnotConfig(id="fd"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_volume_per_band(self) -> None:
        with Tapestry() as t:
            volume = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            FrequencyDecomposer(
                volume=volume,
                center_frequencies_hz=(10.0, 30.0, 60.0),
                _config=KnotConfig(id="fd"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fd"]
        assert isinstance(out, tuple)
        assert len(out) == 3
        for v in out:
            assert isinstance(v, SegyVolume)
