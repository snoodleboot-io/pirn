"""``_RetryResultExtractor`` — final loop state to the public parsed value.

The loop's output is the accumulated ``_RetryState``; ``RetryOnParseFailure``'s
contract is the bare parsed value (or a raised ``ValueError`` on exhaustion).
This knot is the conversion, so the pipeline returns a real sink rather than
a ``Source`` closure wrapping a precomputed value.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.structured_output._retry_state import _RetryState


class _RetryResultExtractor(Knot):
    """Convert the loop's final state into the pipeline's public parsed value."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: Any, **_: Any) -> Any:
        """Extract the parsed value, or raise once retries are exhausted.

        Args:
            state: The loop's final accumulated state.

        Returns:
            The successfully parsed value.

        Raises:
            TypeError: If ``state`` is not the loop's state object.
            ValueError: If the loop exhausted its attempts without parsing.
        """
        if not isinstance(state, _RetryState):
            raise TypeError(
                f"_RetryResultExtractor: state must be a _RetryState, got {type(state).__name__}"
            )
        if not state.succeeded:
            raise ValueError(
                f"RetryOnParseFailure: exhausted {state.attempts} attempt(s); "
                f"last error: {state.last_error}"
            )
        return state.parsed_value
