"""``GovernedDispatch`` — the dispatch path that honours ``KnotConfig.timeout`` and ``retry``.

The engine hands every dispatch through one of these rather than calling its
``Dispatcher`` directly.  Timeout and retry live here, between the engine and
the dispatcher, on purpose: dispatchers stay a single ``dispatch()`` call
(local, thread, Ray, Dask, Celery alike), and ``Knot.__call__`` stays a single
attempt — a retried knot is simply called again with the same inputs.

Algorithm:
    For a knot with ``timeout = t`` (or ``None``) and ``retry = p`` (or
    ``None``):

    0. A knot that fans out (``Knot.fans_out()`` -- a ``Map``/``ZipMap``/
       ``DictMap`` marker on one of its inputs) applies ``t`` and ``p`` to each
       element itself, so this class applies neither: it dispatches once,
       untimed and unretried, and the fan-out bounds, times and retries the
       elements (PIR-873).
    1. Dispatch one attempt on the dispatcher this knot should run on: the
       wrapped dispatcher itself for a leaf, or
       ``dispatcher.dispatcher_for_container(knot)`` for a container
       (``type(knot)._holds_admission_slot`` is ``False`` -- ``SubTapestry``,
       ``LoopSubTapestry``, a loop iteration; PIR-870).  With ``t`` set, the
       attempt runs under ``asyncio.wait_for(…, t)``; on expiry the
       attempt's task is cancelled and the attempt's result is
       ``Err(KnotTimeoutError)``.  ``Knot.__call__`` lets that cancellation
       propagate (PIR-849), which is what makes the expiry observable at
       all.
    2. If the result is not an ``Err``, or ``p`` is ``None``, or
       ``p.should_retry(attempts, err.record)`` is ``False``: return the
       result and the attempt count.
    3. Otherwise, when a *gate* and a *ticket holder* were given: release
       the ticket the holder currently names (unless it holds no slot),
       sleep ``p.delay_before_retry(attempts - 1, err.record)``, then
       re-admit -- blocking on ``gate.wait_for_release()`` between refusals
       -- and store the new ticket back on the holder before the next
       attempt (PIR-870).  Without a gate/holder (e.g. a direct unit test of
       this class), just sleep. Either way, go to 1.

    A real cancellation of the surrounding task — the run being cancelled —
    propagates out of both the attempt and the sleep; it is never retried.

    ```text
    attempts = 0
    loop:
        attempts += 1
        result = attempt(knot, inputs, timeout)          # Err(KnotTimeoutError) on expiry
        if result is not Err or retry is None or not retry.should_retry(attempts, result.record):
            return result, attempts
        if gate and ticket_holder and ticket_holder.ticket.held:
            gate.release(ticket_holder.ticket)
            await sleep(retry.delay_before_retry(attempts - 1, result.record))
            ticket_holder.ticket = await readmit(gate, knot)     # blocks until admitted
        else:
            await sleep(retry.delay_before_retry(attempts - 1, result.record))
    ```

Two properties worth knowing:

* **The timeout bounds each attempt, not the whole retry budget.**  A knot
  with ``timeout=5`` and ``max_attempts=3`` may occupy up to 15 s plus
  backoff.
* **A knot on a worker thread or remote worker is not stopped by the
  timeout.**  ``wait_for`` cancels the awaiting task; a ``ThreadDispatcher``
  thread or a Ray task keeps running until it returns, exactly as on run
  cancellation.  The engine records the timeout and moves on.
* **The admission slot is released during backoff.**  A retrying knot gives
  its slot back before it sleeps and re-admits before its next attempt
  (PIR-870), so a knot sleeping between attempts does not hold capacity
  another ready knot could use.  Re-admission polls the gate directly
  rather than going through the run's ``ReadyQueue``, so a retrying knot can
  cut ahead of a knot that has been waiting longer in the same group; that
  is a fairness nuance, not a correctness one -- the budget itself is never
  exceeded.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

from pirn.core.err import Err
from pirn.exceptions.knot_timeout_error import KnotTimeoutError
from pirn.managers.exception_record import ExceptionRecord

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.core.result import Result
    from pirn.engine.admission.admission import Admission
    from pirn.engine.admission.admission_ticket import AdmissionTicket
    from pirn.engine.admission.admission_ticket_holder import AdmissionTicketHolder
    from pirn.engine.dispatchers.dispatcher import Dispatcher


class GovernedDispatch:
    """Wraps a ``Dispatcher`` with the per-knot timeout and retry the config asks for."""

    def __init__(
        self,
        dispatcher: Dispatcher,
        *,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        rng: Callable[[], float] | None = None,
    ) -> None:
        """Build the governed path over *dispatcher*.

        Args:
            dispatcher: The dispatcher that executes one attempt.
            sleep: Async sleep used between retries; defaults to
                :func:`asyncio.sleep`.  Injected by tests.
            rng: Jitter source forwarded to the retry policy; defaults to
                :func:`random.random`.  Injected by tests.
        """
        self._dispatcher = dispatcher
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._rng = rng

    @property
    def dispatcher(self) -> Dispatcher:
        """The dispatcher executing each attempt."""
        return self._dispatcher

    async def dispatch(
        self,
        knot: Knot,
        inputs: Mapping[str, Any],
        *,
        gate: Admission | None = None,
        ticket_holder: AdmissionTicketHolder | None = None,
    ) -> tuple[Result[Any], int]:
        """Dispatch *knot* under its config's timeout and retry policy.

        Args:
            knot: The run-scoped knot to execute.
            inputs: Its materialized inputs, reused verbatim on every attempt.
            gate: The run's admission gate.  With *ticket_holder* also given,
                a retry's backoff sleep releases the slot and re-admits
                before the next attempt (PIR-870); omit both to sleep
                without touching admission, e.g. a direct unit test of this
                class.
            ticket_holder: Holds the ticket currently backing *knot*'s
                admission.  Updated in place with the freshly re-admitted
                ticket before each retried attempt, so the caller reads back
                whichever ticket is current once dispatch returns.

        Returns:
            The final attempt's result and how many attempts were made.
        """
        config = knot.config
        # A fan-out knot meters, times and retries each element itself
        # (``Knot._fan_out``), so neither belongs around the batch: a
        # batch-level timeout fails every sibling of one slow element, and a
        # batch-level retry re-runs elements that already succeeded (PIR-873).
        fans_out = knot.fans_out()
        policy = None if fans_out else config.retry
        timeout = None if fans_out else config.timeout
        attempts = 0
        while True:
            attempts += 1
            result = await self._attempt(knot, inputs, timeout)
            if policy is None or not isinstance(result, Err):
                return result, attempts
            if not policy.should_retry(attempts, result.record):
                return result, attempts
            delay = policy.delay_before_retry(attempts - 1, result.record, rng=self._rng)
            if gate is not None and ticket_holder is not None:
                await self._release_sleep_and_readmit(gate, ticket_holder, knot, delay)
            else:
                await self._sleep(delay)

    async def _release_sleep_and_readmit(
        self,
        gate: Admission,
        ticket_holder: AdmissionTicketHolder,
        knot: Knot,
        delay: float,
    ) -> None:
        """Give the slot back for the backoff sleep, then re-admit *knot*.

        A container's ticket holds no slot at all (``AdmissionTicket.held``
        is ``False``), so there is nothing to release or re-admit for one --
        it just sleeps, same as with no gate at all.
        """
        current = ticket_holder.ticket
        if not current.held:
            await self._sleep(delay)
            return
        gate.release(current)
        await self._sleep(delay)
        ticket_holder.ticket = await self._readmit(gate, knot)

    @staticmethod
    async def _readmit(gate: Admission, knot: Knot) -> AdmissionTicket:
        """Block until *gate* admits *knot* again, polling on each release."""
        while True:
            ticket = gate.try_admit(knot)
            if ticket is not None:
                return ticket
            await gate.wait_for_release()

    async def _attempt(
        self, knot: Knot, inputs: Mapping[str, Any], timeout: float | None
    ) -> Result[Any]:
        """Run one attempt, converting a timeout into ``Err(KnotTimeoutError)``."""
        dispatcher = (
            self._dispatcher
            if knot.holds_admission_slot()
            else self._dispatcher.dispatcher_for_container(knot)
        )
        if timeout is None:
            return await dispatcher.dispatch(knot, inputs)
        try:
            return await asyncio.wait_for(dispatcher.dispatch(knot, inputs), timeout)
        except TimeoutError:
            return Err(
                record=ExceptionRecord.for_knot(
                    knot.knot_id, KnotTimeoutError(knot.knot_id, timeout)
                )
            )
