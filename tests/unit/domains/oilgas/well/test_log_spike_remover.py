"""Unit tests for :class:`LogSpikeRemover`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.well.log_spike_remover import LogSpikeRemover
from pirn.tapestry import Tapestry


class _LogSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"depth_ft": float(d), "value": 1.0 if d != 5 else 100.0}
            for d in range(1, 12)
        ]


class TestConstruction:
    def test_rejects_even_window_size(self) -> None:
        with pytest.raises(ValueError, match="window_size"):
            with Tapestry():
                src = _LogSource(_config=KnotConfig(id="src"))
                LogSpikeRemover(
                    log_curve=src,
                    window_size=4,
                    mad_threshold=3.0,
                    _config=KnotConfig(id="lsr"),
                )

    def test_rejects_window_size_one(self) -> None:
        with pytest.raises(ValueError, match="window_size"):
            with Tapestry():
                src = _LogSource(_config=KnotConfig(id="src"))
                LogSpikeRemover(
                    log_curve=src,
                    window_size=1,
                    mad_threshold=3.0,
                    _config=KnotConfig(id="lsr"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_removes_spike(self) -> None:
        with Tapestry() as t:
            src = _LogSource(_config=KnotConfig(id="src"))
            LogSpikeRemover(
                log_curve=src,
                window_size=5,
                mad_threshold=2.0,
                _config=KnotConfig(id="lsr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["lsr"]
        assert isinstance(out, list)
        assert len(out) == 11
        spike_entry = next(e for e in out if e["depth_ft"] == 5.0)
        assert spike_entry["spike_removed"] is True

    async def test_no_spike_flag_on_clean_data(self) -> None:
        class _CleanSource(Knot):
            def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
                super().__init__(_config=_config, **kwargs)

            async def process(self, **_: Any) -> list[dict[str, Any]]:
                return [{"depth_ft": float(d), "value": 1.0} for d in range(1, 12)]

        with Tapestry() as t:
            src = _CleanSource(_config=KnotConfig(id="src"))
            LogSpikeRemover(
                log_curve=src,
                window_size=5,
                mad_threshold=2.0,
                _config=KnotConfig(id="lsr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["lsr"]
        assert all(not e["spike_removed"] for e in out)
