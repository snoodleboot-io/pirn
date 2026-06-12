"""``_SQLResponseFormatter`` — internal helper Knot for :class:`SQLAgent`.

Wraps the SQL text plus row results into an :class:`AgentResponse`.
Internal API.

Algorithm:
    1. Receive the ``sql`` query string and ``rows`` list of result rows.
    2. Render each row with ``repr`` and join them with newlines.
    3. Build a content string with an ``SQL:`` block and a ``Rows (N):``
       block.
    4. Return an :class:`AgentResponse` with the content and
       ``finish_reason="stop"``.

Math:
    No numeric computation beyond ``len(rows)`` for the header.

References:
    - AgentResponse dataclass: ``pirn.domains.agents.types.agent_response``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class _SQLResponseFormatter(Knot):
    """Wrap the SQL plus rows into an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        sql: Knot,
        rows: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(sql=sql, rows=rows, _config=_config, **kwargs)

    async def process(
        self,
        sql: str,
        rows: list[Any],
        **_: Any,
    ) -> AgentResponse:
        """Format the SQL query and its result rows into an AgentResponse.

        Args:
            sql: The SQL query string that was executed.
            rows: The list of row values returned by the database.

        Returns:
            An AgentResponse whose content contains the SQL query and a formatted rows block.
        """
        rendered_rows = "\n".join(repr(row) for row in rows)
        content = f"SQL:\n{sql}\n\nRows ({len(rows)}):\n{rendered_rows}"
        return AgentResponse(content=content, finish_reason="stop")

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
