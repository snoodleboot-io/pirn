from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Ok(BaseModel, Generic[T]):
    """Successful knot output wrapping the computed value.

    The ``Ok`` variant of the ``Result`` union indicates that a knot's
    ``process()`` method completed without raising.  The wrapped ``value`` is
    the raw output before any downstream consumer receives it.

    Attributes:
        value: The output produced by the knot.
    """

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
