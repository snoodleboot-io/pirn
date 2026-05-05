"""Unit tests for :class:`MigrationProcessor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.migration_processor import MigrationProcessor
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                MigrationProcessor(
                    volume=volume,
                    method="not_a_method",
                    _config=KnotConfig(id="mig"),
                )

    def test_accepts_valid_methods(self) -> None:
        for method in ("kirchhoff", "rtm", "phase_shift", "stolt"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                m = MigrationProcessor(
                    volume=volume,
                    method=method,
                    _config=KnotConfig(id="mig"),
                )
                assert m.method == method


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_migrated_volume(self) -> None:
        with Tapestry() as t:
            volume = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            MigrationProcessor(
                volume=volume,
                method="kirchhoff",
                _config=KnotConfig(id="mig"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["mig"]
        assert isinstance(out, SegyVolume)
        assert "migrated_kirchhoff" in out.volume_id
