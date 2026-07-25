"""``CassetteEntry`` — one recorded LLM/tool/retrieval I/O keyed by content."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.determinism.content_digest import content_digest
from pirn_agents.determinism.interaction_kind import InteractionKind


@dataclass(frozen=True)
class CassetteEntry(PirnOpaqueValue):
    """A single recorded interaction: its content key, kind, and output.

    ``sequence`` disambiguates repeated calls that share a ``key`` (e.g. a loop
    issuing the same request), so replay serves recorded results in the order
    they were captured.

    Attributes
    ----------
    key:
        The content digest (or caller-supplied id) the interaction is keyed by.
    kind:
        Which class of I/O this entry captured.
    output:
        The JSON-serialisable recorded result served on replay.
    sequence:
        0-based ordinal among entries sharing ``key``.
    """

    key: str
    kind: InteractionKind
    output: Any
    sequence: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key:
            raise TypeError("CassetteEntry: key must be a non-empty str")
        if not isinstance(self.kind, InteractionKind):
            raise TypeError(
                f"CassetteEntry: kind must be an InteractionKind, got {type(self.kind).__name__}"
            )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("CassetteEntry: sequence must be an int")
        if self.sequence < 0:
            raise ValueError(f"CassetteEntry: sequence must be >= 0, got {self.sequence}")

    @staticmethod
    def key_for(request: Any) -> str:
        """Return the content-digest key for a request ``payload``."""
        return content_digest(request)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this entry."""
        return {
            "key": self.key,
            "kind": self.kind.value,
            "output": self.output,
            "sequence": self.sequence,
        }

    @classmethod
    def from_payload(cls, payload: Any) -> CassetteEntry:
        """Reconstruct an entry from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"CassetteEntry.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            key=str(payload["key"]),
            kind=InteractionKind(str(payload["kind"])),
            output=payload["output"],
            sequence=int(payload.get("sequence", 0)),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
