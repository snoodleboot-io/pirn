"""``PydanticValidatorResultExtractor`` — final loop state to the public validated instance.

The loop's output is the accumulated ``PydanticValidatorState``;
``PydanticValidatorPipeline``'s contract is the validated model instance (or
a raised ``ValueError`` on exhaustion). This knot is the conversion,
mirroring ``JsonExtractorResultExtractor``.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import BaseModel

from pirn_agents.specializations.structured_output.pydantic_validator_state import (
    PydanticValidatorState,
)


class PydanticValidatorResultExtractor(Knot):
    """Convert the loop's final state into the pipeline's public validated instance."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: PydanticValidatorState, **_: Any) -> BaseModel:
        """Return the validated instance, or raise once retries are exhausted.

        Args:
            state: The loop's final accumulated state.

        Returns:
            The successfully validated model instance.

        Raises:
            ValueError: If the loop exhausted its attempts without validating.
        """
        if state.validated is None:
            raise ValueError(
                "PydanticValidatorPipeline: exhausted "
                f"{state.attempts} attempt(s); last error: {state.last_error}"
            )
        return state.validated
