"""Unit tests for :class:`DriftMonitor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.production.drift_monitor import DriftMonitor
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_columns(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                DriftMonitor(
                    baseline=_KnotStub(_config=KnotConfig(id="b")),
                    current=_KnotStub(_config=KnotConfig(id="c")),
                    columns=[],
                    _config=KnotConfig(id="dm"),
                )

    def test_rejects_threshold_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                DriftMonitor(
                    baseline=_KnotStub(_config=KnotConfig(id="b")),
                    current=_KnotStub(_config=KnotConfig(id="c")),
                    columns=["feature"],
                    threshold=1.5,
                    _config=KnotConfig(id="dm"),
                )

    def test_rejects_non_knot_baseline(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                DriftMonitor(
                    baseline="bad",  # type: ignore[arg-type]
                    current=_KnotStub(_config=KnotConfig(id="c")),
                    columns=["feature"],
                    _config=KnotConfig(id="dm"),
                )

    def test_attributes_stored(self) -> None:
        with Tapestry():
            dm = DriftMonitor(
                baseline=_KnotStub(_config=KnotConfig(id="b")),
                current=_KnotStub(_config=KnotConfig(id="c")),
                columns=["f1", "f2"],
                threshold=0.2,
                _config=KnotConfig(id="dm"),
            )
        self.assertEqual(dm.columns, ("f1", "f2"))
        self.assertAlmostEqual(dm.threshold, 0.2)
