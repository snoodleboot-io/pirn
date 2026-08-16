"""``TriggeredBatch`` — run a batch once per trigger fire (F28-S5 / PIR-584).

Binds a core :class:`pirn.triggers.base.Trigger` to a
:class:`~pirn_agents.batch.map_agent.MapAgent`: for each fire it fetches a fresh
input set from ``inputs_fn(ordinal)``, runs the batch to completion, and yields a
:class:`~pirn_agents.batch.batch_progress.BatchProgress` summarising that run
(``completed_count`` successes out of ``total`` — the partial-failure report per
fire). It owns no scheduling itself; the trigger decides *when* and this decides
*what*, so a cron/interval schedule and an event source drive the same batch with
no code change.

The loop takes its semantics from :func:`pirn.triggers.base.run_forever`, with
optional ``on_result``/``on_error`` callbacks observing each run. Trigger
lifecycle is the one place it deliberately does not: ``run_forever`` closes the
trigger on every exit path, whereas this leaves a trigger the caller
constructed open unless ``owns_trigger=True`` hands it over. Closing is terminal
for both triggers in this package — a closed ``IntervalTrigger`` yields nothing
and a closed ``EventTrigger`` can never be fed again — so closing one the caller
still holds turns a second run into a silent no-op or a deadlock. Ownership is
therefore explicit and defaults to the caller. It cannot *be* ``run_forever``, which calls
``tapestry.run(request)`` — a ``MapAgent`` is not a ``Tapestry`` (it has no
terminals), and this must stay an ``AsyncIterator[BatchProgress]`` because
streaming per-fire progress to its caller is its whole public contract, whereas
``run_forever`` returns ``None``.

One deliberate departure: ``run_forever`` routes every ``BaseException`` to
``on_error``, so an observer silently swallows cancellation. Here
``asyncio.CancelledError`` is re-raised before ``on_error`` is consulted.

Checkpoint scoping (PIR-803)
----------------------------
The single ``MapAgent`` is reused for every fire, and a ``MapAgent`` re-seeds
its skip-set from its checkpointer on every run. A checkpoint is therefore
scoped to *one fire*: each run is given the fire's ordinal as its
``checkpoint_scope``, so an interrupted fire still resumes where it stopped
while the next fire starts clean. Sharing one namespace across fires instead
made a key that repeats between windows — a customer id, a file name, a
partition key — read as already-done, so a fire could report success having
processed nothing. Callers who genuinely want cross-fire de-duplication ask for
it with ``shared_checkpoint=True``, which is sound only when item keys are
unique across *all* fires.

The fire ordinal is taken from the trigger's own
``request.parameters["fire_ordinal"]`` rather than from a counter local to this
loop, so the ordinal that names the batch, selects the inputs, scopes the
checkpoint, and reaches an ``on_result`` observer are all one number. Carrying
that parameter is a convention of this package's triggers, not something the
core ``Trigger`` base guarantees, so a fire that omits it (or carries a
non-positive-int) falls back to this loop's counter.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable

from pirn.core.run_request import RunRequest
from pirn.triggers.base import Trigger

from pirn_agents.batch.batch_progress import BatchProgress
from pirn_agents.batch.map_agent import MapAgent


class TriggeredBatch:
    """Drive a :class:`MapAgent` once per fire of a core :class:`Trigger`.

    The trigger's lifecycle stays with whoever constructed it unless
    ``owns_trigger=True`` transfers it, so binding a trigger here does not
    consume it and the same trigger can drive another run.
    """

    def __init__(
        self,
        *,
        trigger: Trigger,
        map_agent: MapAgent,
        inputs_fn: Callable[[int], Iterable[object]],
        scope_fn: Callable[[int], str] | None = None,
        batch_id: str = "batch",
        owns_trigger: bool = False,
        shared_checkpoint: bool = False,
        on_result: Callable[[RunRequest, BatchProgress], Awaitable[None]] | None = None,
        on_error: Callable[[RunRequest, BaseException], Awaitable[None]] | None = None,
    ) -> None:
        """Bind the trigger, runner, and per-fire input source.

        Args:
            trigger: The fire source — any core ``Trigger``. Its lifecycle
                belongs to the caller unless ``owns_trigger`` says otherwise.
            map_agent: The configured batch runner invoked on each fire.
            inputs_fn: Maps the fire ordinal to that run's input items — called
                fresh per fire so each run can pick up new data. The ordinal is
                the trigger's own ``fire_ordinal`` where it publishes one, else
                a 1-based counter over this loop's fires.
            scope_fn: Maps the fire ordinal to a **stable identity for the window
                being processed** — a window start timestamp, a partition key, a
                content hash of the inputs. When supplied it, not the ordinal,
                becomes the checkpoint scope.

                Supply it whenever a batch must survive process restarts
                (PIR-813). The ordinal is a per-``stream()`` counter held inside
                the trigger's generator, so a replacement process restarts
                numbering at 1 and fire N of the new process inherits fire N of
                the old one's skip-set — every item already seen under that
                number is silently dropped, including a repeat customer or
                partition key that genuinely needs reprocessing. An identity
                derived from the data does not restart.

                ``inputs_fn`` is called fresh per fire precisely so each run can
                pick up new data, which means the caller already knows which
                window it just produced and is the only party able to name it.
                Left ``None``, the scope falls back to the ordinal — today's
                behaviour, correct for a single long-lived process.
            batch_id: Stable prefix for each run's reported batch id
                (``"<batch_id>-<ordinal>"``).
            owns_trigger: Whether :meth:`run` closes the trigger when it exits.
                Defaults to ``False``: the caller constructed the trigger and
                still holds it, so it stays usable for another run. Pass
                ``True`` for the fire-and-forget shape — a trigger constructed
                inline purely to drive this batch — to get ``run_forever``'s
                always-close semantics and no leak if the consumer walks away.
                Closing is terminal for both triggers in this package, so an
                owned trigger must not be reused.
            shared_checkpoint: Whether every fire shares one checkpoint
                namespace. Defaults to ``False``: each fire checkpoints under
                its own ordinal, so an interrupted fire resumes and a later fire
                never skips work merely because an earlier one used the same
                item key. Pass ``True`` only when item keys are globally unique
                across *all* fires and you want an item completed in one fire
                skipped in every later one — with repeating keys it silently
                drops the whole of a later fire's work. It has no effect unless
                the ``map_agent`` was given a checkpointer.
            on_result: Awaited after each completed run with the fire's
                ``RunRequest`` and the ``BatchProgress`` about to be yielded.
            on_error: Awaited when a run raises, with the fire's ``RunRequest``
                and the exception. Supplying it absorbs the failure so later
                fires still run; without it the exception propagates.
                ``asyncio.CancelledError`` is always re-raised and never
                reaches this callback.

        Raises:
            TypeError: If ``trigger``/``map_agent`` are the wrong type,
                ``owns_trigger``/``shared_checkpoint`` are not ``bool``, or
                ``inputs_fn``/``on_result``/``on_error`` are not callable.
            ValueError: If ``batch_id`` is empty.
        """
        if not isinstance(trigger, Trigger):
            raise TypeError(
                f"TriggeredBatch: trigger must be a Trigger, got {type(trigger).__name__}"
            )
        if not isinstance(map_agent, MapAgent):
            raise TypeError(
                f"TriggeredBatch: map_agent must be a MapAgent, got {type(map_agent).__name__}"
            )
        if not callable(inputs_fn):
            raise TypeError(
                f"TriggeredBatch: inputs_fn must be callable, got {type(inputs_fn).__name__}"
            )
        if scope_fn is not None and not callable(scope_fn):
            raise TypeError(
                f"TriggeredBatch: scope_fn must be callable, got {type(scope_fn).__name__}"
            )
        if on_result is not None and not callable(on_result):
            raise TypeError(
                f"TriggeredBatch: on_result must be callable, got {type(on_result).__name__}"
            )
        if on_error is not None and not callable(on_error):
            raise TypeError(
                f"TriggeredBatch: on_error must be callable, got {type(on_error).__name__}"
            )
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("TriggeredBatch: batch_id must be a non-empty str")
        if not isinstance(owns_trigger, bool):
            raise TypeError(
                f"TriggeredBatch: owns_trigger must be a bool, got {type(owns_trigger).__name__}"
            )
        if not isinstance(shared_checkpoint, bool):
            raise TypeError(
                f"TriggeredBatch: shared_checkpoint must be a bool, "
                f"got {type(shared_checkpoint).__name__}"
            )
        self._trigger = trigger
        self._map_agent = map_agent
        self._inputs_fn = inputs_fn
        self._scope_fn = scope_fn
        # Scopes already used by this instance. A repeated scope would put two
        # fires in one namespace, so the second silently processes nothing
        # (PIR-813); it is rejected rather than allowed to look like success.
        self._seen_scopes: set[str] = set()
        self._batch_id = batch_id
        self._owns_trigger = owns_trigger
        self._shared_checkpoint = shared_checkpoint
        self._on_result = on_result
        self._on_error = on_error

    async def run(self) -> AsyncIterator[BatchProgress]:
        """Run one batch per fire, yielding a :class:`BatchProgress` per run.

        The trigger is left open, so a caller-owned trigger that ends by itself
        — an ``IntervalTrigger`` exhausting ``max_fires``, say — can drive
        another run. When ``owns_trigger`` was set, the trigger is instead
        closed on every exit path (normal end of stream, a propagating error,
        cancellation, or the consumer abandoning this generator), matching
        ``run_forever``; a failure raised by ``close()`` itself is suppressed so
        it cannot mask whatever ended the loop.

        Yields:
            One ``BatchProgress`` per completed fire. A fire whose run failed
            and was absorbed by ``on_error`` yields nothing.
        """
        fires = 0
        try:
            async for request in self._trigger.stream():
                fires += 1
                ordinal = TriggeredBatch._fire_ordinal(request, fires)
                try:
                    progress = await self._run_once(ordinal)
                except asyncio.CancelledError:
                    # run_forever would hand this to on_error; cancellation must
                    # not be observable-and-swallowed, so it always propagates.
                    raise
                except BaseException as exc:
                    if self._on_error is None:
                        raise
                    await self._on_error(request, exc)
                    continue
                if self._on_result is not None:
                    await self._on_result(request, progress)
                yield progress
        finally:
            if self._owns_trigger:
                with contextlib.suppress(Exception):
                    await self._trigger.close()

    @staticmethod
    def _fire_ordinal(request: RunRequest, fallback: int) -> int:
        """Return the trigger's own fire ordinal, or ``fallback`` when unusable.

        The ordinal drives the reported ``batch_id``, the ``inputs_fn`` call and
        the checkpoint scope, so taking it from the request keeps all three in
        step with what an ``on_result`` observer reads off the same request. A
        core ``Trigger`` is not obliged to publish ``fire_ordinal`` — only this
        package's triggers do — so anything missing or not a positive ``int``
        falls back to this loop's own count of fires rather than failing a run
        or, worse, collapsing two fires onto one checkpoint scope.
        """
        ordinal = request.parameters.get("fire_ordinal")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
            return fallback
        return ordinal

    def _checkpoint_scope(self, ordinal: int) -> str:
        """Return this fire's checkpoint scope, rejecting one already used.

        The uniqueness check is what the ordinal never had (PIR-813). A trigger
        publishing a repeated ``fire_ordinal`` — or publishing ``2`` on its first
        fire and omitting it on the second, so the fallback counter also yields
        ``2`` — put two fires in one namespace. The second then found every key
        already checkpointed and processed nothing, while an ``on_result``
        observer saw two fires reporting the same ``batch_id``. That reads as
        success, which is the reason it is worth refusing.

        The guard is per-instance and therefore per-process. It cannot see what a
        previous process did, which is exactly why a caller who needs to survive
        restarts supplies ``scope_fn`` instead of relying on the ordinal.

        Args:
            ordinal: Index of the fire being run.

        Returns:
            The scope string for this fire.

        Raises:
            TypeError: If ``scope_fn`` returned a non-``str``.
            ValueError: If ``scope_fn`` returned an empty string, or the scope
                was already used by an earlier fire on this instance.
        """
        if self._scope_fn is None:
            scope = str(ordinal)
        else:
            scope = self._scope_fn(ordinal)
            if not isinstance(scope, str):
                raise TypeError(
                    f"TriggeredBatch: scope_fn must return a str, got {type(scope).__name__}"
                )
            if not scope:
                raise ValueError("TriggeredBatch: scope_fn must return a non-empty str")
        if scope in self._seen_scopes:
            raise ValueError(
                f"TriggeredBatch: checkpoint scope {scope!r} was already used by an earlier "
                f"fire. Two fires sharing one scope make the second skip every item the first "
                f"completed, so it would report success having processed nothing. "
                f"{'Return a distinct value per window from scope_fn' if self._scope_fn is not None else 'The trigger repeated a fire_ordinal; supply scope_fn to name each window'}."
            )
        self._seen_scopes.add(scope)
        return scope

    async def _run_once(self, ordinal: int) -> BatchProgress:
        """Run one batch for the given fire and summarise it.

        The fire's checkpoint scope is ``scope_fn(ordinal)`` when one was
        supplied and the ordinal otherwise, so a fire interrupted part-way
        resumes from its own checkpoint on a replay while contributing nothing
        to any other fire's skip-set — unless ``shared_checkpoint`` put every
        fire back in one namespace.

        Args:
            ordinal: Index of the fire being run.

        Returns:
            The run's ``BatchProgress`` — ``completed_keys`` for the items that
            succeeded, out of ``total`` attempted.

        Raises:
            TypeError: If ``scope_fn`` returned a non-``str``.
            ValueError: If ``scope_fn`` returned an empty string, or if this
                fire's scope was already used by an earlier fire.
        """
        inputs = self._inputs_fn(ordinal)
        scope = None if self._shared_checkpoint else self._checkpoint_scope(ordinal)
        completed: set[str] = set()
        total = 0
        async for result in self._map_agent.run(inputs, checkpoint_scope=scope):
            total += 1
            if result.succeeded:
                completed.add(result.key)
        return BatchProgress(
            batch_id=f"{self._batch_id}-{ordinal}",
            completed_keys=frozenset(completed),
            total=total,
        )
