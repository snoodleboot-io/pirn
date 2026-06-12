from __future__ import annotations

import traceback
from collections.abc import Callable
from threading import Lock

from pirn.managers.exception_record import ExceptionRecord
from pirn.managers.rebindable_exception import RebindableError


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

        RebindableError instances surface their carried original_exc_type
        and original_traceback_text rather than the wrapper's own type and
        frames, preserving fidelity when an Err from a knot is upgraded to a
        manager-registered record.
        """
        if isinstance(exc, RebindableError):
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
