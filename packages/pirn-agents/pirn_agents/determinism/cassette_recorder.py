"""``CassetteRecorder`` — the mode-aware record/replay engine over a cassette."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn_agents.determinism.cassette import Cassette
from pirn_agents.determinism.cassette_entry import CassetteEntry
from pirn_agents.determinism.interaction_kind import InteractionKind
from pirn_agents.determinism.recording_mode import RecordingMode
from pirn_agents.exceptions.missing_cassette_entry_error import MissingCassetteEntryError


class CassetteRecorder:
    """Route a unit of non-deterministic I/O through record / replay / passthrough.

    The recorder wraps a base :class:`Cassette` (empty by default) and a
    :class:`RecordingMode`. In ``RECORD`` it runs the live ``thunk`` and appends
    the result; in ``REPLAY`` it serves the next recorded output for the key and
    never touches the network; in ``PASSTHROUGH`` it runs live and records
    nothing. Replay position is per-key and lives on the recorder, so the
    underlying cassette stays immutable and reusable.
    """

    def __init__(
        self,
        *,
        cassette: Cassette | None = None,
        mode: RecordingMode = RecordingMode.PASSTHROUGH,
    ) -> None:
        """Initialise the engine over ``cassette`` in ``mode``.

        Args:
            cassette: The tape to replay from / seed the recording with; an empty
                cassette is used when omitted.
            mode: The record/replay/passthrough posture.

        Raises:
            TypeError: If ``cassette`` is not a Cassette or ``mode`` is not a
                RecordingMode.
        """
        if cassette is not None and not isinstance(cassette, Cassette):
            raise TypeError(
                f"CassetteRecorder: cassette must be a Cassette, got {type(cassette).__name__}"
            )
        if not isinstance(mode, RecordingMode):
            raise TypeError(
                f"CassetteRecorder: mode must be a RecordingMode, got {type(mode).__name__}"
            )
        self._mode = mode
        self._base: Cassette = cassette if cassette is not None else Cassette()
        self._recorded: list[CassetteEntry] = list(self._base.entries)
        self._replay_cursor: dict[str, int] = {}

    @property
    def mode(self) -> RecordingMode:
        """Return the recorder's current mode."""
        return self._mode

    @property
    def cassette(self) -> Cassette:
        """Return the cassette holding everything recorded so far."""
        return Cassette(entries=tuple(self._recorded))

    async def invoke(
        self,
        *,
        key: str,
        kind: InteractionKind,
        thunk: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Return the result for ``key``, recording or replaying per the mode.

        Args:
            key: Stable content key for this unit of I/O.
            kind: The interaction kind (for classification and error context).
            thunk: A zero-argument coroutine factory producing the live result.

        Returns:
            The live result (``RECORD`` / ``PASSTHROUGH``) or the recorded output
            (``REPLAY``).

        Raises:
            TypeError: If ``kind`` is not an InteractionKind.
            MissingCassetteEntryError: In ``REPLAY`` when ``key`` has no further
                recorded entry.
        """
        if not isinstance(kind, InteractionKind):
            raise TypeError(
                f"CassetteRecorder.invoke: kind must be an InteractionKind, "
                f"got {type(kind).__name__}"
            )
        if self._mode is RecordingMode.REPLAY:
            return self._replay(key, kind)
        output = await thunk()
        if self._mode is RecordingMode.RECORD:
            sequence = sum(1 for entry in self._recorded if entry.key == key)
            self._recorded.append(
                CassetteEntry(key=key, kind=kind, output=output, sequence=sequence)
            )
        return output

    def _replay(self, key: str, kind: InteractionKind) -> Any:
        """Serve the next recorded output for ``key`` from the base cassette."""
        cursor = self._replay_cursor.get(key, 0)
        matches = self._base.entries_for(key)
        if cursor >= len(matches):
            raise MissingCassetteEntryError(key, kind.value)
        self._replay_cursor[key] = cursor + 1
        return matches[cursor].output
