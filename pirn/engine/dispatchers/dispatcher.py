from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.core.result import Result


class Dispatcher:
    """Interface: runs a knot somewhere and returns its Result.

    Implementations inherit and override dispatch().
    """

    @property
    def name(self) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement name")

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        raise NotImplementedError(f"{type(self).__name__} must implement dispatch()")
