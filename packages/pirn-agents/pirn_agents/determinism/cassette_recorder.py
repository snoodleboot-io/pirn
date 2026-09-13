"""``CassetteRecorder`` — the mode-aware record/replay engine over a cassette.

ADR "agents speaks core" WS3 part 3: a thin adapter over the engine's own
record/replay machinery instead of a bespoke cassette format.

* **RECORD** = a normal ``Tapestry.run()`` of a single knot (``_config.id =
  key``) wrapping ``thunk``; the engine content-addresses the result into
  ``DataStore`` and records lineage under ``RunHistory`` the same as any
  other knot — no separate cassette write.
* **REPLAY** = ``Tapestry.run(replay=ReplaySession.from_history(...))`` over
  the same single-knot shape, sourcing which recorded run to replay from
  ``RunHistory.query_lineage_by_knot_id(key)`` — a real replay, verified
  against the recording, not a raw ``data_store.get``. Constructing with
  ``cassette=`` (a previously-exported, portable :class:`Cassette` — the
  cross-process case ``CassetteStore`` exists for) seeds a fresh
  ``RunHistory``/``DataStore`` with one synthetic recorded run per entry
  before the first call, so the exact same replay path serves it.
* **PASSTHROUGH** = ``await thunk()`` directly, no history/data_store
  interaction at all.

:attr:`cassette` still materialises a :class:`Cassette` snapshot of
everything this recorder instance has recorded, for a caller that wants to
persist it to a :class:`CassetteStore` for portability or diffing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.backends.in_memory.in_memory_data_store import InMemoryDataStore
from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.hashing import content_hash
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_lineage import KnotLineage
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry

from pirn_agents.determinism._thunk_source import _ThunkSource
from pirn_agents.determinism.cassette import Cassette
from pirn_agents.determinism.cassette_entry import CassetteEntry
from pirn_agents.determinism.interaction_kind import InteractionKind
from pirn_agents.determinism.recording_mode import RecordingMode
from pirn_agents.exceptions.missing_cassette_entry_error import MissingCassetteEntryError


class CassetteRecorder:
    """Route a unit of non-deterministic I/O through record / replay / passthrough.

    In ``RECORD`` it runs the live ``thunk`` as a knot and appends the result
    to its own :attr:`cassette` snapshot; in ``REPLAY`` it serves the next
    recorded output for the key through a real engine replay, never touching
    the network; in ``PASSTHROUGH`` it runs live and records nothing.
    """

    def __init__(
        self,
        *,
        cassette: Cassette | None = None,
        mode: RecordingMode = RecordingMode.PASSTHROUGH,
        history: RunHistory | None = None,
        data_store: DataStore | None = None,
    ) -> None:
        """Initialise the engine in ``mode``.

        Args:
            cassette: A previously-exported tape to seed replay from (see
                the class docstring). Ignored outside ``REPLAY``. ``None``
                starts an empty tape.
            mode: The record/replay/passthrough posture.
            history: The ``RunHistory`` record/replay runs are recorded
                to/served from. Defaults to a fresh ``InMemoryHistory``; pass
                a durable backend to share recordings across processes
                without going through a ``Cassette`` export at all.
            data_store: The ``DataStore`` values are content-addressed into.
                Defaults to a fresh ``InMemoryDataStore``.

        Raises:
            TypeError: If ``cassette`` is not a Cassette, ``mode`` is not a
                RecordingMode, or ``history``/``data_store`` are the wrong
                type.
        """
        if cassette is not None and not isinstance(cassette, Cassette):
            raise TypeError(
                f"CassetteRecorder: cassette must be a Cassette, got {type(cassette).__name__}"
            )
        if not isinstance(mode, RecordingMode):
            raise TypeError(
                f"CassetteRecorder: mode must be a RecordingMode, got {type(mode).__name__}"
            )
        if history is not None and not isinstance(history, RunHistory):
            raise TypeError(
                f"CassetteRecorder: history must be a RunHistory, got {type(history).__name__}"
            )
        if data_store is not None and not isinstance(data_store, DataStore):
            raise TypeError(
                f"CassetteRecorder: data_store must be a DataStore, got {type(data_store).__name__}"
            )
        self._mode = mode
        self._history: RunHistory = history if history is not None else InMemoryHistory()
        self._data_store: DataStore = data_store if data_store is not None else InMemoryDataStore()
        self._replay_cursor: dict[str, int] = {}
        self._recorded: list[CassetteEntry] = []
        self._pending_seed: Cassette | None = cassette

    @property
    def mode(self) -> RecordingMode:
        """Return the recorder's current mode."""
        return self._mode

    @property
    def history(self) -> RunHistory:
        """Return the ``RunHistory`` this recorder records to / replays from."""
        return self._history

    @property
    def data_store(self) -> DataStore:
        """Return the ``DataStore`` this recorder content-addresses values into."""
        return self._data_store

    @property
    def cassette(self) -> Cassette:
        """Return a snapshot of everything this recorder instance has recorded."""
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
            key: Stable content key for this unit of I/O — also the knot id
                the engine records/replays it under.
            kind: The interaction kind (for classification and error context).
            thunk: A zero-argument coroutine factory producing the live result.

        Returns:
            The live result (``RECORD`` / ``PASSTHROUGH``) or the recorded
            output (``REPLAY``).

        Raises:
            TypeError: If ``kind`` is not an InteractionKind.
            MissingCassetteEntryError: In ``REPLAY`` when ``key`` has no
                further recorded entry.
        """
        if not isinstance(kind, InteractionKind):
            raise TypeError(
                f"CassetteRecorder.invoke: kind must be an InteractionKind, "
                f"got {type(kind).__name__}"
            )
        if self._mode is RecordingMode.PASSTHROUGH:
            return await thunk()
        if self._mode is RecordingMode.REPLAY:
            return await self._replay(key=key, kind=kind, thunk=thunk)
        return await self._record(key=key, kind=kind, thunk=thunk)

    async def _record(
        self, *, key: str, kind: InteractionKind, thunk: Callable[[], Awaitable[Any]]
    ) -> Any:
        """RECORD: run ``thunk`` as a single-knot Tapestry run and keep the value."""
        with Tapestry(history=self._history, data_store=self._data_store) as tapestry:
            _ThunkSource(_config=KnotConfig(id=key)).bind(thunk)
            run = await tapestry.run(RunRequest())
        value = run.outputs[key]
        sequence = sum(1 for entry in self._recorded if entry.key == key)
        self._recorded.append(CassetteEntry(key=key, kind=kind, output=value, sequence=sequence))
        return value

    async def _replay(
        self, *, key: str, kind: InteractionKind, thunk: Callable[[], Awaitable[Any]]
    ) -> Any:
        """REPLAY: serve the next recorded run for ``key`` via a real engine replay."""
        await self._ensure_seeded()
        rows = await self._history.query_lineage_by_knot_id(key)
        # A replay of this key is itself recorded (core records unconditionally
        # — there is no "don't record" posture), tagged extra["replayed_from_run_id"]
        # by the engine. Excluding those rows keeps the count of "genuinely
        # available" entries fixed at what was actually recorded/seeded, so
        # replaying a key more times than it was recorded still raises
        # MissingCassetteEntryError instead of re-serving an echo of itself.
        ok_rows = [
            row for row in rows if row.outcome == "ok" and "replayed_from_run_id" not in row.extra
        ]
        cursor = self._replay_cursor.get(key, 0)
        if cursor >= len(ok_rows):
            raise MissingCassetteEntryError(key, kind.value)
        run_id = ok_rows[cursor].run_id
        self._replay_cursor[key] = cursor + 1
        session = await ReplaySession.from_history(history=self._history, run_id=run_id)
        with Tapestry(history=self._history, data_store=self._data_store) as tapestry:
            _ThunkSource(_config=KnotConfig(id=key)).bind(thunk)
            run = await tapestry.run(RunRequest(), replay=session)
        return run.outputs[key]

    async def _ensure_seeded(self) -> None:
        """Seed one synthetic recorded run per entry of a ``cassette=`` tape, once."""
        pending, self._pending_seed = self._pending_seed, None
        if pending is None:
            return
        for index, entry in enumerate(pending.entries):
            output_hash = content_hash(entry.output)
            await self._data_store.put(output_hash, entry.output)
            run_id = f"cassette-seed:{entry.key}:{entry.sequence}:{index}"
            now = datetime.now(UTC)
            lineage = KnotLineage(
                run_id=run_id,
                knot_id=entry.key,
                knot_class=f"{_ThunkSource.__module__}.{_ThunkSource.__qualname__}",
                # A _ThunkSource for a given key always builds the identical
                # KnotConfig(id=key) with every other field at its default, and
                # never carries a literal config value (the thunk is stashed as
                # private state, not a tracked config value) — so this is
                # exactly what the engine computes for the real replay call,
                # with no need to construct an actual knot to get it.
                knot_config_hash=content_hash(KnotConfig(id=entry.key).model_dump(mode="json")),
                parent_input_hashes={},
                output_hash=output_hash,
                outcome="ok",
                error_record_id=None,
                skip_reason=None,
                dispatcher="CassetteRecorder",
                started_at=now,
                finished_at=now,
            )
            seeded_run = RunResult(
                run_id=run_id,
                terminals_requested=[entry.key],
                outputs={entry.key: entry.output},
                lineage=[lineage],
                started_at=now,
                finished_at=now,
                dispatcher="CassetteRecorder",
                parent_run_id=None,
                parent_knot_id=None,
                actor=None,
                trigger=None,
            )
            await self._history.record_run(seeded_run)
