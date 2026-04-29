"""Exception capture, recording, and reporting.

Knots never raise into the engine; the engine catches everything and hands
it to ``ExceptionManager.record(...)``, which produces an
``ExceptionRecord`` with a stable id and stores it under the run.
Downstream knots see ``Err(record)`` and act per their ``error_policy``.

Phase 2 changes from Phase 1
----------------------------
* ``ExceptionRecord`` now carries an explicit ``id`` field, referenced by
  ``KnotLineage.error_record_id``.
* The manager exposes ``get(record_id)`` for lineage joins.
* A dedicated ``RebindableException`` class lets the engine carry a
  placeholder record's pre-computed type/traceback through the manager
  without resorting to attribute probing on arbitrary exceptions.
"""

from __future__ import annotations

import re as _re
import traceback
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock

from pydantic import BaseModel, ConfigDict, Field

_SECRET_PATTERNS = [
    _re.compile(r'(://)[^@\s"\']+(@)'),
    _re.compile(r'(?i)\b(password|passwd|api_?key|token|secret|auth)\s*[=:]\s*\S+'),
    _re.compile(r'(?i)(Authorization:\s*\w+\s+)\S+'),
]


def redact_common_secrets(text: str) -> str:
    """Replace common credential patterns in a traceback with <redacted>.

    Pass this as ``traceback_filter`` to ``ExceptionManager`` or
    ``Tapestry`` to reduce the risk of credentials appearing in stored
    exception records.

    Patterns matched:

    * DSN credentials: ``postgresql://user:pass@host`` → ``postgresql://<redacted>@host``
    * Named credential assignments: ``password=s3cr3t``, ``api_key=xyz``, etc.
    * Authorization header values: ``Authorization: Bearer <token>``
    """
    # DSN credentials
    text = _re.sub(r'(://)[^@\s"\']+(@)', r'\1<redacted>\2', text)
    # Named credential assignments
    text = _re.sub(
        r'(?i)\b(password|passwd|api_?key|token|secret|auth)\s*[=:]\s*\S+',
        r'\1=<redacted>',
        text,
    )
    # Authorization header values
    text = _re.sub(r'(?i)(Authorization:\s*\w+\s+)\S+', r'\1<redacted>', text)
    return text


class ExceptionRecord(BaseModel):
    """A captured exception, detached from frames, safe to serialise."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(
        default_factory=lambda: f"exc-{uuid.uuid4().hex[:12]}",
        description="Run-scoped identifier; lineage records refer to this.",
    )
    run_id: str
    knot_id: str
    exc_type: str
    message: str
    traceback_text: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RebindableException(Exception):
    """Carrier for a placeholder record's identity when re-registering it
    with the live ``ExceptionManager``.

    A knot's ``__call__`` may produce an ``Err`` containing a placeholder
    ``ExceptionRecord`` (with run_id="<unbound>") because at the time
    the knot raised, the engine's manager wasn't in scope.  When the
    engine catches that Err it constructs a ``RebindableException``
    carrying the placeholder's ``exc_type`` and ``traceback_text``, then
    hands it back to ``ExceptionManager.record(...)``, which produces a
    real record using those carried fields rather than re-deriving from
    the wrapper exception's own frames.

    This is a normal class with explicit attributes; the manager
    recognises it by ``isinstance``.
    """

    def __init__(
        self,
        exc_type: str,
        message: str,
        traceback_text: str,
    ) -> None:
        super().__init__(message)
        self.original_exc_type = exc_type
        self.original_traceback_text = traceback_text


class ExceptionManager:
    """Per-run store of captured exceptions."""

    def __init__(
        self,
        run_id: str,
        traceback_filter: Callable[[str], str] | None = None,
    ) -> None:
        self._run_id = run_id
        self._traceback_filter = traceback_filter
        self._records: list[ExceptionRecord] = []
        self._by_id: dict[str, ExceptionRecord] = {}
        self._lock = Lock()

    def record(self, knot_id: str, exc: BaseException) -> ExceptionRecord:
        """Capture an exception and return the registered record.

        ``RebindableException`` instances surface their carried
        ``original_exc_type`` and ``original_traceback_text`` rather
        than the wrapper's own type and frames; this preserves fidelity
        when an ``Err`` from a knot is upgraded to a
        manager-registered record.
        """
        if isinstance(exc, RebindableException):
            exc_type = exc.original_exc_type
            traceback_text = exc.original_traceback_text
        else:
            exc_type = type(exc).__name__
            traceback_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if self._traceback_filter is not None:
            traceback_text = self._traceback_filter(traceback_text)
        rec = ExceptionRecord(
            run_id=self._run_id,
            knot_id=knot_id,
            exc_type=exc_type,
            message=str(exc),
            traceback_text=traceback_text,
        )
        with self._lock:
            self._records.append(rec)
            self._by_id[rec.id] = rec
        return rec

    def get(self, record_id: str) -> ExceptionRecord | None:
        with self._lock:
            return self._by_id.get(record_id)

    def report(self) -> list[ExceptionRecord]:
        with self._lock:
            return list(self._records)

    def has_failures(self) -> bool:
        with self._lock:
            return bool(self._records)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
