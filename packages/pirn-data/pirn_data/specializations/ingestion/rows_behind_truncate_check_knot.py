"""``RowsBehindTruncateCheckKnot`` — pass through ``rows`` only after the
``gate`` upstream knot has produced its output.

Used by :class:`FullRefreshExtract` to force the target table truncate
to complete before the insert sink reads the extracted rows. The output
is the unchanged row list.

Algorithm:
    1. Declare both ``rows`` and ``gate`` as upstream Knot dependencies,
       so the engine schedules this knot only after both have resolved.
    2. Ignore ``gate``'s resolved value entirely — its only purpose is to
       make the truncate a scheduling predecessor of this knot.
    3. Return ``rows`` unchanged.

    ```text
    await gate   # scheduling side-effect only; value discarded
    return rows  # unchanged
    ```

References:
    [1] docs/contributing/knot-design-rules.md — ordering-dependency
        pattern for a Knot whose sole purpose is to sequence execution.
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
