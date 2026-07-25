"""``DeterminismContext`` — the seed + clock bundle threaded through a run."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.determinism.clock import Clock
from pirn_agents.determinism.deterministic_rng import DeterministicRng
from pirn_agents.determinism.frozen_clock import FrozenClock
from pirn_agents.determinism.system_clock import SystemClock


class DeterminismContext(PirnOpaqueValue):
    """The injectable determinism controls for one run: a clock and an RNG.

    Threaded through a run so nothing reads the wall clock or the global RNG
    directly. :meth:`deterministic` builds a frozen-clock + seeded-RNG context
    whose time and randomness are byte-reproducible; :meth:`live` builds a
    real-clock context with a seeded RNG for production. :meth:`rng_for` hands out
    independent, reproducible sub-streams by label.
    """

    def __init__(self, *, clock: Clock, rng: DeterministicRng, deterministic: bool) -> None:
        """Initialise with an injected ``clock`` and ``rng``.

        Raises:
            TypeError: If ``clock`` is not a Clock or ``rng`` is not a
                DeterministicRng.
        """
        if not isinstance(clock, Clock):
            raise TypeError(
                f"DeterminismContext: clock must be a Clock, got {type(clock).__name__}"
            )
        if not isinstance(rng, DeterministicRng):
            raise TypeError(
                f"DeterminismContext: rng must be a DeterministicRng, got {type(rng).__name__}"
            )
        self._clock = clock
        self._rng = rng
        self._deterministic = bool(deterministic)

    @classmethod
    def deterministic(cls, *, seed: int, epoch: datetime | None = None) -> DeterminismContext:
        """Build a reproducible context: a :class:`FrozenClock` + seeded RNG."""
        return cls(
            clock=FrozenClock(epoch=epoch),
            rng=DeterministicRng(seed=seed),
            deterministic=True,
        )

    @classmethod
    def live(cls, *, seed: int = 0) -> DeterminismContext:
        """Build a production context: a real :class:`SystemClock` + seeded RNG."""
        return cls(clock=SystemClock(), rng=DeterministicRng(seed=seed), deterministic=False)

    @property
    def clock(self) -> Clock:
        """Return the injected clock."""
        return self._clock

    @property
    def rng(self) -> DeterministicRng:
        """Return the run's root RNG."""
        return self._rng

    @property
    def is_deterministic(self) -> bool:
        """Return ``True`` when time and randomness are frozen/reproducible."""
        return self._deterministic

    def rng_for(self, label: str) -> DeterministicRng:
        """Return an independent reproducible sub-stream keyed by ``label``."""
        return self._rng.fork(label)

    def to_payload(self) -> dict[str, Any]:
        """Return JSON-friendly determinism metadata for a trajectory."""
        return {"seed": self._rng.seed, "deterministic": self._deterministic}

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
