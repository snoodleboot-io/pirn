"""Unit tests for :class:`SourceLocalizer`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.source_localizer import SourceLocalizer
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_signal(self) -> None:
        with pytest.raises(TypeError, match="SignalFrame"):
            SourceLocalizer(
                signal="x",  # type: ignore[arg-type]
                method="mne",
                source_labels=[],
                _config=KnotConfig(id="s"),
            )

    def test_rejects_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="method"):
            SourceLocalizer(
                signal=SignalFrame(),
                method="bogus",
                source_labels=[],
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="source_labels"):
            SourceLocalizer(
                signal=SignalFrame(),
                method="mne",
                source_labels=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_string_label(self) -> None:
        with pytest.raises(TypeError, match="string"):
            SourceLocalizer(
                signal=SignalFrame(),
                method="mne",
                source_labels=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="s"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_source_mapping(self) -> None:
        with Tapestry() as t:
            SourceLocalizer(
                signal=SignalFrame(),
                method="dspm",
                source_labels=["lh.frontal"],
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, Mapping)
        assert "lh.frontal" in out
