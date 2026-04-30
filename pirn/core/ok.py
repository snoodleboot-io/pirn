from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

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
