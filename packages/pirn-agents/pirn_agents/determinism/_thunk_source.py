"""``_ThunkSource`` — runs an injected zero-arg async thunk as a knot's output."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source


class _ThunkSource(Source):
    """Wraps an arbitrary async thunk so :class:`CassetteRecorder` can run or
    replay it as an ordinary knot.

    The thunk is stashed as private mutable state, never passed through the
    standard config-value path: a callable has no canonical content hash
    (``InvocationIdentity`` treats it as ``unhashable``), so tracking it as a
    literal constructor argument would make ``config_values_hash`` differ —
    or worse, collapse to the shared "unhashable" marker — between the
    recording call and every later replay of the same key, which is exactly
    the shape ``ReplaySession`` refuses to trust (see
    ``InvocationIdentity.is_comparable``). Structurally this knot always has
    the same (empty) parent set and the same ``KnotConfig`` for a given key,
    which is all replay actually needs to compare.
    """

    def __init__(self, *, thunk: Callable[[], Awaitable[Any]], _config: KnotConfig) -> None:
        super().__init__(_config=_config)
        self._mutable_thunk = thunk

    async def process(self, **_: Any) -> Any:
        return await self._mutable_thunk()
