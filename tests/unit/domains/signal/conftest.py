"""Shared fixtures for signal-domain unit tests.

The signal knots accept ``signal: Knot`` parents that resolve to
:class:`SignalFrame` values at runtime. Tests build a tiny upstream
knot via the ``@knot`` factory that emits a deterministic frame so we
can assert against exact lineage shape.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pirn.core.knot_factory import knot
from pirn.domains.signal.types.signal_frame import SignalFrame

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
