from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pirn.engine.dispatchers.dispatcher import Dispatcher

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.core.result import Result


class LocalDispatcher(Dispatcher):
    """Run knots in the current event loop.

    Trivially awaits knot(inputs).  Knot.__call__ catches all exceptions
    and wraps results, so this dispatcher does nothing else.
    """

    @property
    def name(self) -> str:
        return "LocalDispatcher"

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        return await knot(inputs)
