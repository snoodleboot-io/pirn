"""``RowsBehindTruncateCheckKnot`` — pass through ``rows`` only after the
``gate`` upstream knot has produced its output.

Used by :class:`FullRefreshExtract` to force the target table truncate
to complete before the insert sink reads the extracted rows. The output
is the unchanged row list.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class RowsBehindTruncateCheckKnot(Knot):
    """Pass through ``rows`` once ``gate`` has resolved."""

    def __init__(
        self,
        *,
        rows: Knot,
        gate: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(rows=rows, gate=gate, _config=_config, **kwargs)

    async def process(self, rows: Any, gate: Any, **_: Any) -> Any:
        """Pass through rows unchanged after the gate dependency has resolved.

        Args:
            rows: The upstream rows value to pass through.
            gate: The upstream gate dependency that must resolve before rows are forwarded.

        Returns:
            The rows value, unchanged.
        """
        return rows
