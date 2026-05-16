from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pirn.managers.exception_record import ExceptionRecord


class Err(BaseModel):
    """Failed knot output carrying a reference to the registered exception record.

    The ``Err`` variant of the ``Result`` union indicates that a knot's
    ``process()`` method raised an exception.  The exception is not stored
    inline; instead an ``ExceptionRecord`` is registered with the run's
    ``ExceptionManager`` and this object holds a reference to that record.
    This keeps ``Err`` itself small and serialisable while still allowing
    full traceback retrieval.

    Calling ``unwrap()`` on an ``Err`` always raises ``RuntimeError``; guard
    with ``is_err`` or pattern-match on the ``Result`` union before unwrapping.

    Attributes:
        record: The ``ExceptionRecord`` registered by the engine for the
            exception that caused this failure.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    record: ExceptionRecord

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_err(self) -> bool:
        return True

    @property
    def is_skipped(self) -> bool:
        return False

    def unwrap(self) -> object:  # pragma: no cover
        raise RuntimeError(
            f"unwrap() called on Err; underlying exception was "
            f"{self.record.exc_type}: {self.record.message}"
        )
