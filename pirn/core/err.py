from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pirn.managers.exception_record import ExceptionRecord


class Err(BaseModel):
    """Failed knot output, carrying a reference to the registered exception record."""

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
