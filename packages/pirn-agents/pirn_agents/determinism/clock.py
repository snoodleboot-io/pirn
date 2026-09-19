"""``Clock`` — the injectable time source threaded through a run.

Nothing in a deterministic run may call the wall clock directly (``Date.now`` /
``datetime.now`` / ``time.monotonic``); every time read goes through an injected
:class:`Clock`. Production runs use
:class:`~pirn_agents.determinism.system_clock.SystemClock`; deterministic runs use
:class:`~pirn_agents.determinism.frozen_clock.FrozenClock` so timestamps are
reproducible.

A clock is also a knot input: a writer that stamps ``stored_at`` takes one
rather than calling ``datetime.now`` in its ``process()`` (PIR-873), so it mixes
in :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` — the same treatment
:class:`~pirn_agents.memory.stores.memory_store.MemoryStore` gets — and IO
validation of a ``Clock``-typed parameter is an ``isinstance`` check rather than
a descent into whatever the implementation holds.
"""

from __future__ import annotations

from datetime import datetime

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class Clock(PirnOpaqueValue):
    """Interface for a time source: a wall-clock instant and a monotonic tick."""

    def now(self) -> datetime:
        """Return the current instant as a timezone-aware :class:`datetime`."""
        raise NotImplementedError(f"{type(self).__name__} must implement now()")

    def monotonic(self) -> float:
        """Return a monotonically non-decreasing tick in fractional seconds."""
        raise NotImplementedError(f"{type(self).__name__} must implement monotonic()")
