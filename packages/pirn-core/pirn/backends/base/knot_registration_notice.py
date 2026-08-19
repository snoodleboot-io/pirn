"""Wire format carrying run attribution alongside a knot registration."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from typing import Any

from pirn.tapestry import _run_id_scope, current_run_id


class KnotRegistrationNotice:
    """A knot-registration event plus the run that registered it.

    ``InMemoryStore`` calls subscribers synchronously inside the
    registering task, so the ambient run id that PIR-808's
    ``_RunScopedSubscriber`` reads is right for free.  The durable stores
    do not: ``PostgresStore`` delivers from a background LISTEN task and
    ``ValKeyStore`` from a pub/sub callback on a dedicated connection.
    Neither inherits the registering task's context — and worse, whatever
    context they *do* carry is an accident of which run happened to
    subscribe first.  Run attribution therefore has to travel in the
    notification payload and be rebound around delivery, which is what
    this class exists to do (PIR-815).

    Encoding is JSON so the payload stays self-describing and fits inside
    the 8000-byte Postgres ``NOTIFY`` limit with room to spare.
    """

    _knot_id_field = "knot_id"
    _run_id_field = "run_id"

    def __init__(self, knot_id: str, run_id: str | None) -> None:
        """Initialise the notice.

        Args:
            knot_id: Identifier of the knot that was registered.
            run_id: The run that registered it, or ``None`` when the
                registration was made with no run in scope.
        """
        self._knot_id = knot_id
        self._run_id = run_id

    @property
    def knot_id(self) -> str:
        """Identifier of the knot that was registered."""
        return self._knot_id

    @property
    def run_id(self) -> str | None:
        """The registering run, or ``None`` if the registration is unowned."""
        return self._run_id

    @classmethod
    def for_current_run(cls, knot_id: str) -> KnotRegistrationNotice:
        """Build a notice stamped with the ambient run id.

        Must be called in the registering context — for both durable
        stores that is inside ``aregister``, which runs under a copy of
        the caller's context whether it was awaited directly, scheduled
        with ``ensure_future``, or driven by ``asyncio.run``.

        Args:
            knot_id: Identifier of the knot being registered.

        Returns:
            A notice carrying ``knot_id`` and the current run id.
        """
        return cls(knot_id, current_run_id())

    def encode(self) -> str:
        """Serialise to a notification payload.

        Returns:
            A JSON object string suitable for ``pg_notify`` or ``PUBLISH``.
        """
        return json.dumps({self._knot_id_field: self._knot_id, self._run_id_field: self._run_id})

    @classmethod
    def decode(cls, payload: str) -> KnotRegistrationNotice:
        """Parse a notification payload.

        A payload written by a publisher from before PIR-815 is a bare
        knot id with no attribution.  It decodes to ``run_id=None``,
        which is the same thing an unowned registration decodes to, and
        is delivered on the same broadcast terms.  That is deliberate: in
        a mixed-version window the alternative is to drop those
        registrations, trading a visible cross-run result for silently
        lost work — the trade PIR-808 explicitly refused.  Broadcasting
        reproduces exactly the behaviour such a deployment already has.

        Anything that is not a JSON object carrying a string ``knot_id``
        is treated as a bare knot id, so a knot whose id happens to be
        valid JSON still round-trips.

        Args:
            payload: The raw notification payload.

        Returns:
            The decoded notice.
        """
        try:
            parsed: Any = json.loads(payload)
        except ValueError:
            return cls(payload, None)
        if not isinstance(parsed, dict):
            return cls(payload, None)
        knot_id: Any = parsed.get(cls._knot_id_field)
        if not isinstance(knot_id, str):
            return cls(payload, None)
        run_id: Any = parsed.get(cls._run_id_field)
        return cls(knot_id, run_id if isinstance(run_id, str) else None)

    def run_scope(self) -> AbstractContextManager[None]:
        """Rebind ambient run identity to the registering run.

        Wrap subscriber dispatch in this so that code past the
        ``subscribe()`` seam reads run identity the same way it does
        under ``InMemoryStore``.

        Returns:
            A context manager binding ``current_run_id()`` to
            :attr:`run_id` for the duration of the block.
        """
        return _run_id_scope(self._run_id)
