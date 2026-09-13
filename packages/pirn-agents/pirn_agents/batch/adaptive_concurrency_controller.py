"""``AdaptiveConcurrencyController`` — AIMD concurrency control on the core admission gate.

ADR agents-speaks-core, WS4b: this used to be a bare AIMD counter that
``MapAgent`` read on every dispatch to compute its own ``asyncio.wait``
bound (a private, engine-invisible concurrency limit). It is now an
:class:`~pirn.engine.admission.admission_observer.AdmissionObserver`: the
engine calls its ``on_admit``/``on_release`` hooks as knots of its group
take and free their slot, and it reacts by calling
``AdmissionGate.set_limit`` directly — the same "AIMD governor" math, now
steering the run's real admission budget instead of a shadow one.

Two signals drive the AIMD, matching the pre-migration behaviour exactly:

* **Increase** — additive, on every ``on_release`` whose knot's group
  matches and whose outcome was ``"ok"``. This is a generic, always-safe
  signal: ``AdmissionEvent`` exposes outcome and group, nothing provider-
  specific.
* **Decrease** — multiplicative, but *only* from :meth:`on_throttle`, called
  directly by the per-item knot
  (:class:`~pirn_agents.batch._map_item._MapItem`) when it observes a
  :class:`~pirn_agents.batch.rate_limit_signal.RateLimitSignal`.
  ``AdmissionEvent`` carries only a coarse ``"ok"/"err"/"skipped"/"aborted"``
  outcome — not *why* a knot failed — so backing off on every ``"err"``
  would also fire on an ordinary bug in the per-item callable, which the
  pre-migration controller never did (only ``RateLimitSignal`` triggered a
  decrease). Routing the decrease through the direct call the rate-limited
  knot already makes preserves that distinction without widening
  ``AdmissionEvent``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.engine.admission.admission_observer import AdmissionObserver

if TYPE_CHECKING:
    from pirn.engine.admission.admission_event import AdmissionEvent
    from pirn.engine.admission.admission_gate import AdmissionGate


class AdaptiveConcurrencyController(AdmissionObserver):
    """A time-free AIMD governor that steers a run's ``AdmissionGate`` limit."""

    def __init__(
        self,
        *,
        min_limit: int = 1,
        max_limit: int = 8,
        initial: int | None = None,
        increase: float = 1.0,
        decrease_factor: float = 0.5,
        group: str | None = None,
    ) -> None:
        """Build the controller.

        Args:
            min_limit: Floor the limit never drops below. Must be >= 1.
            max_limit: Ceiling the limit never climbs above. Must be >= min.
            initial: Starting limit; defaults to ``max_limit`` (optimistic start,
                backing off on the first throttle).
            increase: Additive step added per successful release. Must be > 0.
            decrease_factor: Multiplier applied on a throttle (0 < f < 1).
            group: The ``KnotConfig.concurrency_group`` this controller
                governs. ``on_admit``/``on_release`` ignore events for any
                other group, since one gate serves every group of a run.

        Raises:
            ValueError: If any bound is out of range.
        """
        if isinstance(min_limit, bool) or not isinstance(min_limit, int) or min_limit < 1:
            raise ValueError(
                f"AdaptiveConcurrencyController: min_limit must be >= 1, got {min_limit!r}"
            )
        if isinstance(max_limit, bool) or not isinstance(max_limit, int) or max_limit < min_limit:
            raise ValueError(
                f"AdaptiveConcurrencyController: max_limit must be >= min_limit, got {max_limit!r}"
            )
        if isinstance(increase, bool) or not isinstance(increase, (int, float)) or increase <= 0:
            raise ValueError(
                f"AdaptiveConcurrencyController: increase must be > 0, got {increase!r}"
            )
        if (
            isinstance(decrease_factor, bool)
            or not isinstance(decrease_factor, (int, float))
            or not 0 < decrease_factor < 1
        ):
            raise ValueError(
                f"AdaptiveConcurrencyController: decrease_factor must be in (0, 1), "
                f"got {decrease_factor!r}"
            )
        start = max_limit if initial is None else initial
        if start < min_limit or start > max_limit:
            raise ValueError(
                f"AdaptiveConcurrencyController: initial must be within "
                f"[{min_limit}, {max_limit}], got {start}"
            )
        self._min = min_limit
        self._max = max_limit
        self._increase = float(increase)
        self._decrease = float(decrease_factor)
        self._limit = float(start)
        self._group = group
        self._gate: AdmissionGate | None = None

    def limit(self) -> int:
        """The current integer concurrency limit, clamped to ``[min, max]``."""
        return max(self._min, min(self._max, int(self._limit)))

    def bind_to_group(self, group: str | None) -> None:
        """Set the concurrency group this controller reacts to and steers.

        Called by :class:`~pirn_agents.batch.map_agent.MapAgent` so a
        controller built standalone (with no ``group=`` of its own) still
        governs whichever group that particular batch's items were placed
        in, without the caller having to know the group name up front.

        Args:
            group: The ``KnotConfig.concurrency_group`` to govern.
        """
        self._group = group

    def on_admit(self, event: AdmissionEvent) -> None:
        """Remember the run's gate so :meth:`on_throttle` can steer it too."""
        if event.group != self._group:
            return
        self._gate = event.gate

    def on_release(self, event: AdmissionEvent) -> None:
        """Additively increase the limit on a successful release of this group."""
        if event.group != self._group:
            return
        gate = event.gate
        self._gate = gate
        if event.outcome == "ok":
            self._limit = min(float(self._max), self._limit + self._increase)
            gate.set_limit(self._group, self.limit())

    def on_throttle(self, retry_after: float | None = None) -> None:
        """Multiplicatively decrease the limit on an observed rate-limit signal.

        Called directly by the per-item knot when it sees a
        :class:`~pirn_agents.batch.rate_limit_signal.RateLimitSignal` — the
        engine's ``AdmissionEvent`` stream cannot tell a throttle apart from
        any other failure, so this is the one place the decision is made.

        Args:
            retry_after: The signal's ``retry_after`` hint, unused by the
                limit math itself (that lives on the shared token bucket);
                accepted so a caller can pass the signal's attribute straight
                through without unpacking it first.
        """
        self._limit = max(float(self._min), self._limit * self._decrease)
        if self._gate is not None:
            self._gate.set_limit(self._group, self.limit())
