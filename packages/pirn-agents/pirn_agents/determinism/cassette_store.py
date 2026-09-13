"""``CassetteStore`` — the provider-neutral persistence interface for cassettes.

.. deprecated:: ADR agents-speaks-core WS3 part 3
    :class:`~pirn_agents.determinism.cassette_recorder.CassetteRecorder`
    records to and replays from ``RunHistory``/``DataStore`` directly now — a
    named cassette store is no longer where a live recording lives. This
    interface (and :class:`~pirn_agents.determinism.in_memory_cassette_store.InMemoryCassetteStore`
    / :class:`~pirn_agents.determinism.file_cassette_store.FileCassetteStore`)
    stays importable for a caller that still wants to export/import a
    portable :class:`~pirn_agents.determinism.cassette.Cassette` snapshot —
    ``CassetteRecorder(cassette=...)`` accepts one to seed replay from.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.determinism.cassette import Cassette


class CassetteStore(PirnOpaqueValue):
    """Interface every cassette store must satisfy, keyed by a cassette name.

    A store persists a named :class:`Cassette`. Implementations may keep tapes in
    process or serialise them to disk; recorders depend only on this interface.
    The default in-process and stdlib-JSON adapters need no heavy backend.
    """

    async def save(self, name: str, cassette: Cassette) -> None:
        """Persist ``cassette`` under ``name``, replacing any prior tape."""
        raise NotImplementedError(f"{type(self).__name__} must implement save()")

    async def load(self, name: str) -> Cassette | None:
        """Return the cassette stored under ``name``, or ``None`` if absent."""
        raise NotImplementedError(f"{type(self).__name__} must implement load()")

    async def delete(self, name: str) -> None:
        """Remove the cassette stored under ``name`` if present."""
        raise NotImplementedError(f"{type(self).__name__} must implement delete()")

    async def list_cassettes(self) -> Sequence[str]:
        """Return the names of all stored cassettes."""
        raise NotImplementedError(f"{type(self).__name__} must implement list_cassettes()")
