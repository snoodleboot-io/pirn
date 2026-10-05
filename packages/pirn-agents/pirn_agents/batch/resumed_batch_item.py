"""``ResumedBatchItem`` — ask history whether one batch item already succeeded.

One knot per item, so each resume probe has its own ``Result``, retry, timeout
and lineage row rather than being one turn of a Python loop the run cannot see
(Rule 11; PIR-874). The probes are independent — each asks about its own item
id — so the engine may run them together, which also means a thousand-item
resume is one round of concurrent reads rather than a thousand sequential ones.

``RunHistory`` has no bulk "which of these knot ids succeeded" query, so the
probe is per item either way; what changes is whether the run can see them.

Internal API. See ``map_agent.py``.
"""

from __future__ import annotations

from typing import Any

from pirn.backends.base.run_history import RunHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ResumedBatchItem(Knot):
    """Report whether an item's knot id already has a successful lineage row."""

    def __init__(
        self,
        *,
        history: Knot | RunHistory,
        item_id: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(history=history, item_id=item_id, _config=_config, **kwargs)

    async def process(self, history: Any, item_id: str, **_: Any) -> bool:
        """Return whether ``item_id`` ran successfully before.

        ``history`` is typed ``Any`` rather than ``RunHistory`` for the reason
        ``MapAgent.process`` documents for ``dispatcher``: the core base carries
        no pydantic core schema, so an annotated parameter makes every knot
        construction raise. ``MapAgent`` has already resolved and checked it.

        Args:
            history: The ``RunHistory`` the previous attempt was recorded to.
            item_id: The item's knot id, ``<batch_id>:<key>``.

        Returns:
            ``True`` if any recorded invocation of ``item_id`` was ``ok``.
        """
        rows = await history.query_lineage_by_knot_id(item_id)
        return any(row.outcome == "ok" for row in rows)
