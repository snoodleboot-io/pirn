"""``FileCassetteStore`` — a stdlib-JSON, file-serialisable :class:`CassetteStore`."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pirn_agents.determinism.cassette import Cassette
from pirn_agents.determinism.cassette_store import CassetteStore


class FileCassetteStore(CassetteStore):
    """Persist each cassette as one ``<root>/<name>.json`` file using the stdlib.

    No heavy backend is required — cassettes are canonical JSON on disk, so a
    recorded suite is committable and replays identically across machines. Names
    are sanitised to a safe filename stem to keep the store self-contained.
    """

    def __init__(self, root: str | Path) -> None:
        """Initialise the store rooted at ``root`` (created on first save)."""
        self._root = Path(root)

    def _path_for(self, name: str) -> Path:
        """Return the JSON file path backing cassette ``name``."""
        safe = "".join(ch if (ch.isalnum() or ch in {"-", "_", "."}) else "_" for ch in name)
        return self._root / f"{safe}.json"

    async def save(self, name: str, cassette: Cassette) -> None:
        """Serialise ``cassette`` to ``<root>/<name>.json``.

        Raises:
            TypeError: If ``cassette`` is not a Cassette.
        """
        if not isinstance(cassette, Cassette):
            raise TypeError(
                f"FileCassetteStore: cassette must be a Cassette, got {type(cassette).__name__}"
            )
        self._root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(cassette.to_payload(), sort_keys=True, indent=2)
        self._path_for(name).write_text(payload, encoding="utf-8")

    async def load(self, name: str) -> Cassette | None:
        """Return the cassette deserialised from disk, or ``None`` if absent."""
        path = self._path_for(name)
        if not path.is_file():
            return None
        return Cassette.from_payload(json.loads(path.read_text(encoding="utf-8")))

    async def delete(self, name: str) -> None:
        """Remove the cassette file for ``name`` if present."""
        self._path_for(name).unlink(missing_ok=True)

    async def list_cassettes(self) -> Sequence[str]:
        """Return the sorted names of all stored cassette files."""
        if not self._root.is_dir():
            return []
        return sorted(path.stem for path in self._root.glob("*.json"))
