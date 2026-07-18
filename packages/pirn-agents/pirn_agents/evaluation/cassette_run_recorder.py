"""``CassetteRunRecorder`` — the F29 cassette-backed :class:`RunRecorder` (closes F12's seam).

F12's :func:`~pirn_agents.evaluation.run_eval.run_eval` routes every target
invocation through the :class:`~pirn_agents.evaluation.run_recorder.RunRecorder`
seam, defaulting to the live
:class:`~pirn_agents.evaluation.null_run_recorder.NullRunRecorder`. This class is
the concrete recorder F29 promised: it adapts the eval seam onto F29's
:class:`~pirn_agents.determinism.cassette_recorder.CassetteRecorder`, so a whole
suite records once and then replays deterministically offline with no model/tool
I/O and no change to the runner.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn_agents.determinism.cassette import Cassette
from pirn_agents.determinism.cassette_recorder import CassetteRecorder
from pirn_agents.determinism.interaction_kind import InteractionKind
from pirn_agents.determinism.recording_mode import RecordingMode
from pirn_agents.evaluation.run_recorder import RunRecorder


class CassetteRunRecorder(RunRecorder):
    """A :class:`RunRecorder` that records/replays eval I/O through a cassette.

    Each ``invoke(key, thunk)`` is delegated to a wrapped
    :class:`CassetteRecorder` under a fixed :class:`InteractionKind` (``LLM`` by
    default — the target call is a model interaction from the runner's view). The
    recorder's mode decides whether the eval item runs live and records, replays a
    recorded result, or passes through.
    """

    def __init__(
        self,
        *,
        recorder: CassetteRecorder,
        kind: InteractionKind = InteractionKind.LLM,
    ) -> None:
        """Wrap ``recorder`` for use as an eval record/replay seam.

        Raises:
            TypeError: If ``recorder`` is not a CassetteRecorder or ``kind`` is not
                an InteractionKind.
        """
        if not isinstance(recorder, CassetteRecorder):
            raise TypeError(
                f"CassetteRunRecorder: recorder must be a CassetteRecorder, "
                f"got {type(recorder).__name__}"
            )
        if not isinstance(kind, InteractionKind):
            raise TypeError(
                f"CassetteRunRecorder: kind must be an InteractionKind, got {type(kind).__name__}"
            )
        self._recorder = recorder
        self._kind = kind

    @classmethod
    def replaying(cls, cassette: Cassette) -> CassetteRunRecorder:
        """Build a recorder that replays ``cassette`` (no live I/O)."""
        return cls(recorder=CassetteRecorder(cassette=cassette, mode=RecordingMode.REPLAY))

    @classmethod
    def recording(cls) -> CassetteRunRecorder:
        """Build a recorder that runs live and records into a fresh cassette."""
        return cls(recorder=CassetteRecorder(mode=RecordingMode.RECORD))

    @property
    def cassette(self) -> Cassette:
        """Return the cassette holding everything recorded so far."""
        return self._recorder.cassette

    async def invoke(self, *, key: str, thunk: Callable[[], Awaitable[Any]]) -> Any:
        """Record or replay the eval target's result for ``key`` via the cassette."""
        return await self._recorder.invoke(key=key, kind=self._kind, thunk=thunk)
