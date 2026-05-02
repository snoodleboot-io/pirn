"""``SpecialistFanOutCollector`` — pass-through collector knot.

Inner stage knot used by :class:`ParallelSpecialistFanOut`. The fan-out
itself is performed concurrently outside the inner tapestry; this knot
re-publishes the collected responses as the inner pipeline's output so
the SubTapestry contract — "do real work via an inner tapestry" — is
preserved and the collected mapping appears in the run history.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class SpecialistFanOutCollector(Knot):
    """Echoes a name → :class:`AgentResponse` mapping unchanged."""

    def __init__(
        self,
        *,
        responses: Mapping[str, AgentResponse],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(responses, Mapping):
            raise TypeError(
                "SpecialistFanOutCollector: responses must be a Mapping, "
                f"got {type(responses).__name__}"
            )
        super().__init__(responses=responses, _config=_config, **kwargs)

    async def process(
        self,
        responses: Mapping[str, AgentResponse],
        **_: Any,
    ) -> Mapping[str, AgentResponse]:
        for name, candidate in responses.items():
            if not isinstance(name, str):
                raise TypeError(
                    "SpecialistFanOutCollector: keys must be strings, "
                    f"got {type(name).__name__}"
                )
            if not isinstance(candidate, AgentResponse):
                raise TypeError(
                    f"SpecialistFanOutCollector: responses[{name!r}] must be "
                    f"an AgentResponse, got {type(candidate).__name__}"
                )
        return dict(responses)
