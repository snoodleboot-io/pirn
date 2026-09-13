"""Interface for watching a run's admissions and steering its limits."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.engine.admission.admission_event import AdmissionEvent


class AdmissionObserver:
    """Interface: hears every admission and release of a run's gate.

    Attach one through ``Tapestry(admission_observers=[...])`` or
    ``tapestry.run(admission_observers=[...])``.  Both hooks default to
    doing nothing, so an observer overrides only what it needs -- the
    ``Emitter`` convention.  Each event carries the gate, so an adaptive
    controller is an observer that calls ``event.gate.set_limit(...)`` from
    ``on_release`` when it sees a throttled outcome or a growing queue
    (ADR agents-speaks-core, WS0).

    Hooks are called synchronously on the engine's loop, between an
    admission or completion and the next scheduling step, so they must be
    quick and must not await.  An exception raised by a hook is logged at
    WARNING and otherwise ignored: an observer can never break a run.
    """

    def on_admit(self, event: AdmissionEvent) -> None:
        """A knot took its slot and is about to be dispatched.

        Args:
            event: The admission, with ``kind == "admit"``.
        """

    def on_release(self, event: AdmissionEvent) -> None:
        """A knot gave its slot back, with its outcome known.

        Args:
            event: The release, with ``kind == "release"`` and ``outcome``
                and ``held_seconds`` filled in.
        """
