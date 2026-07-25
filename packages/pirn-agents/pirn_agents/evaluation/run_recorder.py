"""``RunRecorder`` — the record/replay seam for deterministic evals (F29).

The :func:`~pirn_agents.evaluation.run_eval.run_eval` runner routes every unit of
model/tool I/O for an item through a ``RunRecorder`` keyed by a stable string.
The default :class:`~pirn_agents.evaluation.null_run_recorder.NullRunRecorder`
simply executes the work live (no recording), so evals run over stub or live
providers today.

Deterministic replay via cassettes is **F29's** deliverable (Phase 5, not yet
merged): F29 will provide a cassette-backed ``RunRecorder`` that records each
key's result on first run and replays it thereafter, making a full suite cheap
and reproducible. This interface is the documented seam it plugs into; this
package intentionally does not implement cassettes itself.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class RunRecorder:
    """Interface wrapping one unit of evaluation I/O for record/replay.

    Implementations decide whether to execute ``thunk`` live, replay a recorded
    result for ``key``, or record a fresh one. The runner treats the recorder as
    opaque, so swapping in F29's cassette recorder needs no runner change.
    """

    async def invoke(self, *, key: str, thunk: Callable[[], Awaitable[Any]]) -> Any:
        """Return the result for ``key``, executing or replaying as appropriate.

        Args:
            key: Stable identifier for this unit of I/O (e.g. the eval item id).
            thunk: A zero-argument coroutine factory producing the live result.

        Returns:
            The awaited result of ``thunk`` (or a replayed equivalent).
        """
        raise NotImplementedError(f"{type(self).__name__} must implement invoke()")
