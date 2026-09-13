"""``_JsonExtractorResultExtractor`` — final loop state to the public parsed mapping.

The loop's output is the accumulated ``_JsonExtractorState``;
``JsonExtractorPipeline``'s contract is the bare parsed mapping (or a raised
``ValueError`` on exhaustion). This knot is the conversion, mirroring
``_RetryResultExtractor``.

Internal API. See PIR-856.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.structured_output._json_extractor_state import (
    _JsonExtractorState,
)


class _JsonExtractorResultExtractor(Knot):
    """Convert the loop's final state into the pipeline's public parsed mapping."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: _JsonExtractorState, **_: Any) -> Mapping[str, Any]:
        """Return the parsed mapping, or raise once retries are exhausted.

        Args:
            state: The loop's final accumulated state.

        Returns:
            The successfully parsed mapping.

        Raises:
            ValueError: If the loop exhausted its attempts without parsing.
        """
        if state.result is None:
            raise ValueError(
                f"JsonExtractorPipeline: exhausted {state.attempts} attempt(s); "
                f"last error: {state.last_error}"
            )
        return state.result
