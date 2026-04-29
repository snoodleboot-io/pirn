"""Result type — every knot output is Ok, Err, or Skipped.

Phase 2 extension over Phase 1: ``Skipped`` is its own variant rather than
a sentinel.  An Optional knot that opts out, a Branch's non-selected
children, and a Gate that closes all produce ``Skipped`` — distinct from
``Err`` so downstream knots' ``error_policy`` can react differently.

All three variants are Pydantic models, frozen at construction.  This
matches the rest of the codebase (``KnotConfig``, ``KnotLineage``,
``ExceptionRecord``, etc. are all Pydantic) — the engine produces tens
to hundreds of these per run, and Pydantic's per-construction overhead
is negligible relative to the actual knot work.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from pirn.managers.exceptions import ExceptionRecord

T = TypeVar("T")


class Ok(BaseModel, Generic[T]):
    """Successful knot output."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    value: T

    @property
    def is_ok(self) -> bool:
        return True

    @property
    def is_err(self) -> bool:
        return False

    @property
    def is_skipped(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value


class Err(BaseModel):
    """Failed knot output, carrying a reference to the registered
    exception record."""

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

    def unwrap(self) -> object:  # pragma: no cover — explicit error path
        raise RuntimeError(
            f"unwrap() called on Err; underlying exception was "
            f"{self.record.exc_type}: {self.record.message}"
        )


class Skipped(BaseModel):
    """A knot that was deliberately not run (Optional opt-out, branch path
    not selected, gate closed).  Distinct from ``Err`` so downstream knots
    can treat skip-vs-fail differently.

    Carries an optional ``reason`` for observability.
    """

    model_config = ConfigDict(frozen=True)

    reason: str = "skipped"
    # Optional metadata for inspection (e.g. which branch was chosen).
    detail: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_err(self) -> bool:
        return False

    @property
    def is_skipped(self) -> bool:
        return True

    def unwrap(self) -> object:  # pragma: no cover
        raise RuntimeError(f"unwrap() called on Skipped: {self.reason}")


# Result is one of Ok[T] | Err | Skipped.
Result = Ok[T] | Err | Skipped
