"""``InMemoryCassetteStore`` — a zero-dependency in-process :class:`CassetteStore`."""

from __future__ import annotations

from collections.abc import Sequence

from pirn_agents.determinism.cassette import Cassette
from pirn_agents.determinism.cassette_store import CassetteStore


class InMemoryCassetteStore(CassetteStore):
    """A dict-backed reference :class:`CassetteStore` for tests and single runs."""

    def __init__(self) -> None:
        """Initialise an empty store."""
        self._cassettes: dict[str, Cassette] = {}

    async def save(self, name: str, cassette: Cassette) -> None:
        """Persist ``cassette`` under ``name``.

        Raises:
            TypeError: If ``cassette`` is not a Cassette.
        """
        if not isinstance(cassette, Cassette):
            raise TypeError(
                f"InMemoryCassetteStore: cassette must be a Cassette, got {type(cassette).__name__}"
            )
        self._cassettes[name] = cassette

    async def load(self, name: str) -> Cassette | None:
        """Return the cassette stored under ``name``, or ``None``."""
        return self._cassettes.get(name)

    async def delete(self, name: str) -> None:
        """Remove the cassette stored under ``name`` if present."""
        self._cassettes.pop(name, None)

    async def list_cassettes(self) -> Sequence[str]:
        """Return the sorted names of all stored cassettes."""
        return sorted(self._cassettes)
