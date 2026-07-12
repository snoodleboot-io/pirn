"""``CompactionKnot`` — run a compaction strategy inside the graph.

Algorithm:
    1. Receive the resolved ``strategy`` and ``request``.
    2. Validate input types at process time.
    3. Delegate to :meth:`CompactionStrategy.compact`.
    4. Return the :class:`CompactionResult`.


References:
    - :class:`pirn_agents.context.compaction_strategy.CompactionStrategy`
    - :class:`pirn_agents.context.compaction_request.CompactionRequest`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.context.compaction_request import CompactionRequest
from pirn_agents.context.compaction_result import CompactionResult
from pirn_agents.context.compaction_strategy import CompactionStrategy


class CompactionKnot(Knot):
    """Runs a :class:`CompactionStrategy` over a :class:`CompactionRequest`."""

    def __init__(
        self,
        *,
        strategy: Knot | CompactionStrategy,
        request: Knot | CompactionRequest,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            strategy=strategy,
            request=request,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        strategy: CompactionStrategy,
        request: CompactionRequest,
        **_: Any,
    ) -> CompactionResult:
        """Compact ``request`` with ``strategy`` and return the result.

        Args:
            strategy: The compaction strategy to apply.
            request: The compaction request bundle.

        Returns:
            The :class:`CompactionResult`.

        Raises:
            TypeError: If ``strategy`` is not a CompactionStrategy or ``request``
                is not a CompactionRequest.
        """
        if not isinstance(strategy, CompactionStrategy):
            raise TypeError(
                "CompactionKnot: strategy must be a CompactionStrategy, "
                f"got {type(strategy).__name__}"
            )
        if not isinstance(request, CompactionRequest):
            raise TypeError(
                f"CompactionKnot: request must be a CompactionRequest, got {type(request).__name__}"
            )
        return await strategy.compact(request)
