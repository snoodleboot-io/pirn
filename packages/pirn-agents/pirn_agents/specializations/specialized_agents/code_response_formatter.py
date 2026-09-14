"""``CodeResponseFormatter`` — internal helper Knot for :class:`CodeAgent`.

Wraps the generated code plus linter warnings into an
:class:`AgentResponse`. Internal API.

Algorithm:
    1. Receive the generated ``code`` string and ``warnings`` list from
       the linter knot.
    2. Build a ``usage`` dict recording the count of lint warnings and a
       ``tests_skipped`` sentinel.
    3. Return an :class:`AgentResponse` with ``content=code``,
       ``finish_reason="stop"``, and the usage dict.

Math:
    No numeric computation beyond ``len(warnings)``.

References:
    - AgentResponse dataclass: ``pirn_agents.types.messaging.agent_response``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_response import AgentResponse


class CodeResponseFormatter(Knot):
    """Wrap the code plus linter warnings into an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        code: Knot,
        warnings: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            code=code,
            warnings=warnings,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        code: str,
        warnings: list[str],
        **_: Any,
    ) -> AgentResponse:
        """Combine code and lint warnings into an AgentResponse with a usage summary.

        Args:
            code: The generated code string to surface as the response content.
            warnings: The list of lint warning strings produced by the linter.

        Returns:
            An AgentResponse whose content is the code and usage metadata records lint_warnings count.
        """
        usage: dict[str, int] = {
            "lint_warnings": len(warnings),
            "tests_skipped": 1,
        }
        return AgentResponse(
            content=code,
            finish_reason="stop",
            usage=usage,
        )
