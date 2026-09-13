"""``_LoopTerminal`` — identity knot marking ``LoopSubTapestry`` completion."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot


class _LoopTerminal(Knot):
    """Identity knot — marks loop completion and surfaces the final state."""

    async def process(self, state: Any, **_: Any) -> Any:  # type: ignore[override]
        """Return the final loop state unchanged to surface loop completion.

        Args:
            state: Terminal state value produced by the last iteration chain knot.

        Returns:
            The state value unchanged, making it the observable output of the loop.
        """
        return state
