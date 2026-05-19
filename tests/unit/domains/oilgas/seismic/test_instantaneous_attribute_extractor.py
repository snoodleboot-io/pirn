"""Unit tests for :class:`InstantaneousAttributeExtractor`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.instantaneous_attribute_extractor import (
    InstantaneousAttributeExtractor,
)

_TRACE: dict[str, Any] = {"samples": [0.0, 1.0, -1.0, 0.5], "sample_interval_ms": 4.0}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> InstantaneousAttributeExtractor:
        return InstantaneousAttributeExtractor(
            trace=None,  # type: ignore[arg-type]
            attributes=("amplitude", "phase"),
            _config=KnotConfig(id="iae", validate_io=False),
        )

    async def test_rejects_unknown_attribute(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "unknown attributes"):
            await knot.process(trace=_TRACE, attributes=("amplitude", "bogus"))

    async def test_returns_requested_attributes(self) -> None:
        knot = self._make_knot()
        out = await knot.process(trace=_TRACE, attributes=("amplitude", "phase"))
        assert "amplitude" in out
        assert "phase" in out
        assert "frequency" not in out
        assert len(out["amplitude"]) == 4
