"""Unit tests for :class:`SpectrumObjectStoreDisassembler`."""

from __future__ import annotations

import io
import unittest

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.disassemblers.spectrum_object_store_disassembler import (
    SpectrumObjectStoreDisassembler,
)
from pirn_signal.types.spectrum_frame import SpectrumFrame
from pirn_signal.types.spectrum_payload import SpectrumPayload


def _payload_param() -> Parameter:
    return Parameter("payload", SpectrumPayload, _config=KnotConfig(id="payload"))


def _make() -> SpectrumObjectStoreDisassembler:
    return SpectrumObjectStoreDisassembler(
        payload=_payload_param(),
        _config=KnotConfig(id="disassembler"),
    )


def _spectrum_payload(bins: int = 8) -> SpectrumPayload:
    frame = SpectrumFrame(
        signal_id="spec-01",
        frequency_bins=bins,
        frequency_resolution_hz=1.953,
    )
    data = np.arange(bins, dtype=complex)
    return SpectrumPayload(metadata=frame, data=data)


class TestSpectrumObjectStoreDisassembler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_bytes(self) -> None:
        knot = _make()
        result = await knot.process(payload=_spectrum_payload())
        assert isinstance(result, bytes)
        assert len(result) > 0

    async def test_round_trips_spectral_array(self) -> None:
        knot = _make()
        payload = _spectrum_payload()
        result = await knot.process(payload=payload)
        with np.load(io.BytesIO(result)) as npz:
            np.testing.assert_array_equal(npz["data"], payload.data)
            assert str(npz["signal_id"]) == "spec-01"

    async def test_rejects_non_spectrum_payload(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="payload must be SpectrumPayload"):
            await knot.process(payload={"not": "a payload"})

    async def test_rejects_empty_data(self) -> None:
        knot = _make()
        frame = SpectrumFrame(signal_id="empty", frequency_bins=0, frequency_resolution_hz=0.0)
        empty_payload = SpectrumPayload(metadata=frame, data=np.zeros(0, dtype=complex))
        with pytest.raises(ValueError, match=r"payload\.data must be non-empty"):
            await knot.process(payload=empty_payload)
