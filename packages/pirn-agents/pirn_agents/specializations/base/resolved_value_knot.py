"""``ResolvedValueKnot`` — promote an already-resolved value into a graph node.

A :class:`~pirn.nodes.sub_tapestry.SubTapestry` builds its inner graph inside
``process()``, at which point every input it declared has already been
resolved to a plain value (Rule 2, ``knot-design-rules.md``). Wiring that value
into a fan-out marker (:class:`~pirn.nodes.map_markers.Map`,
:class:`~pirn.nodes.map_markers.ZipMap`, :class:`~pirn.nodes.map_markers.DictMap`)
or an :class:`~pirn.nodes.aggregator.Aggregator` parent requires a *knot*, not a
bare value — those primitives fan out over, or wait on, a source knot. This
knot closes that gap: it takes a resolved value as a config input and returns
it unchanged, so any already-known value can re-enter the inner graph as a
real node with its own lineage row.

Algorithm:
    1. Resolution — the engine (or the caller, synchronously inside a
       ``SubTapestry.process()``) resolves ``value``.
    2. Pass-through — ``process()`` returns ``value`` unchanged.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ResolvedValueKnot(Knot):
    """Wrap an already-resolved value so it can re-enter the graph as a knot."""

    def __init__(
        self,
        *,
        value: Knot | Any,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(value=value, _config=_config, **kwargs)

    async def process(self, value: Any, **_: Any) -> Any:
        """Return ``value`` unchanged.

        Args:
            value: The value to surface as this knot's output.

        Returns:
            ``value``, unchanged.
        """
        return value
