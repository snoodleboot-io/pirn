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

    def dispatcher_for_container(self, knot: Knot) -> Dispatcher:
        """Return the dispatcher a *container* knot should run on instead of this one.

        A container knot (``SubTapestry``, ``LoopSubTapestry``, a loop
        iteration -- ``type(knot)._holds_admission_slot`` is ``False``)
        spends nearly all of its time awaiting its own inner run rather than
        doing work itself; it is I/O-shaped, not CPU- or blocking-I/O-shaped.
        The default answer is this dispatcher itself: most dispatchers run a
        container exactly like any other knot. A dispatcher whose ordinary
        path would waste a scarce resource on that wait -- a
        ``ThreadDispatcher`` pool worker sitting idle while the container's
        inner leaves queue up for the very same pool -- overrides this to
        hand back something cheaper (PIR-870).

        Args:
            knot: The container knot about to be dispatched.

        Returns:
            The dispatcher to run *knot* on.  Defaults to ``self``.
        """
        return self
