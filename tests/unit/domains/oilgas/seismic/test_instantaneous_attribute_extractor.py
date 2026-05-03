"""Unit tests for :class:`InstantaneousAttributeExtractor`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.instantaneous_attribute_extractor import (
    InstantaneousAttributeExtractor,
)
from pirn.tapestry import Tapestry


class _TraceSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"samples": [0.0, 1.0, -1.0, 0.5], "sample_interval_ms": 4.0}


class TestConstruction:
    def test_rejects_unknown_attribute(self) -> None:
        with pytest.raises(ValueError, match="unknown attributes"):
            with Tapestry():
                src = _TraceSource(_config=KnotConfig(id="src"))
                InstantaneousAttributeExtractor(
                    trace=src,
                    attributes=("amplitude", "bogus"),
                    _config=KnotConfig(id="iae"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_requested_attributes(self) -> None:
        with Tapestry() as t:
            src = _TraceSource(_config=KnotConfig(id="src"))
            InstantaneousAttributeExtractor(
                trace=src,
                attributes=("amplitude", "phase"),
                _config=KnotConfig(id="iae"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["iae"]
        assert "amplitude" in out
        assert "phase" in out
        assert "frequency" not in out
        assert len(out["amplitude"]) == 4
