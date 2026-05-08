"""Shared fixtures for signal-domain unit tests.

The signal knots accept ``signal: Knot`` parents that resolve to
:class:`SignalFrame` or :class:`SignalPayload` values at runtime.
Tests build a tiny upstream knot via the ``@knot`` factory that emits
a deterministic frame/payload so we can assert against exact lineage shape.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from pirn.core.knot_factory import knot
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload

_FIXED_FETCHED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def make_signal_frame(
    *,
    signal_id: str = "test",
    channel_count: int = 1,
    sample_rate_hz: float = 1000.0,
    samples_per_channel: int = 1024,
) -> SignalFrame:
    """Construct a deterministic :class:`SignalFrame` for tests."""

    return SignalFrame(
        signal_id=signal_id,
        channel_count=channel_count,
        sample_rate_hz=sample_rate_hz,
        samples_per_channel=samples_per_channel,
        fetched_at=_FIXED_FETCHED_AT,
    )


def make_signal_payload(
    *,
    signal_id: str = "test",
    channel_count: int = 1,
    sample_rate_hz: float = 1000.0,
    samples_per_channel: int = 1024,
) -> SignalPayload:
    """Construct a deterministic :class:`SignalPayload` for tests."""

    frame = SignalFrame(
        signal_id=signal_id,
        channel_count=channel_count,
        sample_rate_hz=sample_rate_hz,
        samples_per_channel=samples_per_channel,
        fetched_at=_FIXED_FETCHED_AT,
    )
    data = np.zeros((channel_count, samples_per_channel)) if channel_count > 1 else np.zeros(samples_per_channel)
    return SignalPayload(frame=frame, data=data)


@pytest.fixture()
def signal_frame() -> SignalFrame:
    """A deterministic single-channel :class:`SignalFrame`."""

    return make_signal_frame()


@knot
async def emit_signal_frame() -> SignalFrame:
    """Upstream knot emitting a deterministic :class:`SignalFrame`."""

    return SignalFrame(
        signal_id="test",
        channel_count=1,
        sample_rate_hz=1000.0,
        samples_per_channel=1024,
        fetched_at=_FIXED_FETCHED_AT,
    )


@knot
async def emit_reference_frame() -> SignalFrame:
    """Upstream knot emitting a deterministic reference :class:`SignalFrame`."""

    return SignalFrame(
        signal_id="reference",
        channel_count=1,
        sample_rate_hz=1000.0,
        samples_per_channel=1024,
        fetched_at=_FIXED_FETCHED_AT,
    )


@knot
async def emit_signal_b_frame() -> SignalFrame:
    """Upstream knot emitting a second :class:`SignalFrame` with same rate."""

    return SignalFrame(
        signal_id="other",
        channel_count=1,
        sample_rate_hz=1000.0,
        samples_per_channel=1024,
        fetched_at=_FIXED_FETCHED_AT,
    )


@knot
async def emit_signal_payload() -> SignalPayload:
    """Upstream knot emitting a deterministic :class:`SignalPayload`."""

    frame = SignalFrame(
        signal_id="test",
        channel_count=1,
        sample_rate_hz=1000.0,
        samples_per_channel=1024,
        fetched_at=_FIXED_FETCHED_AT,
    )
    return SignalPayload(frame=frame, data=np.zeros(1024))


@knot
async def emit_signal_payload_b() -> SignalPayload:
    """Upstream knot emitting a second :class:`SignalPayload` with same rate."""

    frame = SignalFrame(
        signal_id="other",
        channel_count=1,
        sample_rate_hz=1000.0,
        samples_per_channel=1024,
        fetched_at=_FIXED_FETCHED_AT,
    )
    return SignalPayload(frame=frame, data=np.zeros(1024))


@knot
async def emit_spectrum_payload() -> SpectrumPayload:
    """Upstream knot emitting a deterministic :class:`SpectrumPayload`."""

    frame = SpectrumFrame(signal_id="spec", frequency_bins=257, frequency_resolution_hz=1.953)
    return SpectrumPayload(frame=frame, data=np.zeros(257, dtype=complex))
