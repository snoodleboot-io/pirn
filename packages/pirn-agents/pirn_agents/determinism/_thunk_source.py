"""``_ThunkSource`` — runs an injected zero-arg async thunk as a knot's output."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source


class _ThunkSource(Source):
    """Wraps an arbitrary async thunk so :class:`CassetteRecorder` can run or
    replay it as an ordinary knot.

    The thunk is bound via :meth:`bind` — after construction, not as an
    ``__init__`` parameter — so the constructor stays the pure ``_config``
    wiring Knot Design Rule 1 requires (agents-owned knots get no core-lane
    exemption for framework-internal mutable state the way
    ``pirn.nodes.gate.Gate``/``WithContinuation`` do). It could not be a
    tracked config value either way: a callable has no canonical content hash
    (``InvocationIdentity`` treats it as ``unhashable``), so ``config_values_hash``
    would collapse to the shared "unhashable" marker for every instance,
    which ``ReplaySession`` refuses to trust (see
    ``InvocationIdentity.is_comparable``) — every replay would raise rather
    than serve the recording. Structurally this knot always has the same
    (empty) parent set and the same ``KnotConfig`` for a given key, which is
    all replay actually needs to compare.
    """

    def __init__(self, *, _config: KnotConfig) -> None:
        super().__init__(_config=_config)

    def bind(self, thunk: Callable[[], Awaitable[Any]]) -> _ThunkSource:
        """Attach ``thunk`` and return ``self``, for construction one-liners."""
        self._mutable_thunk = thunk
        return self

    async def process(self, **_: Any) -> Any:
        return await self._mutable_thunk()
