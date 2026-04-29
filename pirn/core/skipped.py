from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Skipped(BaseModel):
    """A knot that was deliberately not run.

    Produced by Optional opt-out, non-selected Branch path, or closed Gate.
    Distinct from Err so downstream knots can treat skip-vs-fail differently.
    """

    model_config = ConfigDict(frozen=True)

    reason: str = "skipped"
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
