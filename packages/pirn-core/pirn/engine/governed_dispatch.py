"""``GovernedDispatch`` — the dispatch path that honours ``KnotConfig.timeout`` and ``retry``.

The engine hands every dispatch through one of these rather than calling its
``Dispatcher`` directly.  Timeout and retry live here, between the engine and
the dispatcher, on purpose: dispatchers stay a single ``dispatch()`` call
(local, thread, Ray, Dask, Celery alike), and ``Knot.__call__`` stays a single
attempt — a retried knot is simply called again with the same inputs.

Algorithm:
    For a knot with ``timeout = t`` (or ``None``) and ``retry = p`` (or
    ``None``):

    1. Dispatch one attempt.  With ``t`` set, the attempt runs under
       ``asyncio.wait_for(…, t)``; on expiry the attempt's task is cancelled
       and the attempt's result is ``Err(KnotTimeoutError)``.  ``Knot.__call__``
       lets that cancellation propagate (PIR-849), which is what makes the
       expiry observable at all.
    2. If the result is not an ``Err``, or ``p`` is ``None``, or
       ``p.should_retry(attempts, err.record)`` is ``False``: return the
       result and the attempt count.
    3. Otherwise sleep ``p.delay_before_retry(attempts - 1, err.record)`` on
       the event loop and go to 1.

    A real cancellation of the surrounding task — the run being cancelled —
    propagates out of both the attempt and the sleep; it is never retried.

    ```text
    attempts = 0
    loop:
        attempts += 1
        result = attempt(knot, inputs, timeout)          # Err(KnotTimeoutError) on expiry
        if result is not Err or retry is None or not retry.should_retry(attempts, result.record):
            return result, attempts
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
* **The admission slot is held across backoff.**  A retrying knot keeps the
  slot its admission took while it sleeps; giving it back and re-admitting
  is a later refinement, noted on ``AdmissionTicket``.
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

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> tuple[Result[Any], int]:
        """Dispatch *knot* under its config's timeout and retry policy.

        Args:
            knot: The run-scoped knot to execute.
            inputs: Its materialized inputs, reused verbatim on every attempt.

        Returns:
            The final attempt's result and how many attempts were made.
        """
        config = knot.config
        policy = config.retry
        attempts = 0
        while True:
            attempts += 1
            result = await self._attempt(knot, inputs, config.timeout)
            if policy is None or not isinstance(result, Err):
                return result, attempts
            if not policy.should_retry(attempts, result.record):
                return result, attempts
            await self._sleep(policy.delay_before_retry(attempts - 1, result.record, rng=self._rng))

    async def _attempt(
        self, knot: Knot, inputs: Mapping[str, Any], timeout: float | None
    ) -> Result[Any]:
        """Run one attempt, converting a timeout into ``Err(KnotTimeoutError)``."""
        if timeout is None:
            return await self._dispatcher.dispatch(knot, inputs)
        try:
            return await asyncio.wait_for(self._dispatcher.dispatch(knot, inputs), timeout)
        except TimeoutError:
            return Err(
                record=ExceptionRecord.for_knot(
                    knot.knot_id, KnotTimeoutError(knot.knot_id, timeout)
                )
            )
