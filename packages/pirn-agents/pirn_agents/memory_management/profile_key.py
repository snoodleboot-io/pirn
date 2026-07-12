"""``ProfileKey`` — the provider-neutral session-key abstraction for profiles.

A profile is durable state keyed to a *subject* (a user or an entity), not to any
single conversation. :class:`ProfileKey` is that key: a ``namespace``
(``"user"`` / ``"entity"``) plus a ``subject_id``, yielding a deterministic
:attr:`storage_key` under which the profile is stored/read through the standard
:class:`~pirn_agents.memory_store.MemoryStore` interface.

F14 SEAM
--------
``session_id`` is deliberately a plain optional string, not a durable-session
object. This is the documented plug point for **F14 (durable sessions, Phase 4,
not yet merged)**: today a caller passes whatever session identifier it has (or
``None``); when F14 lands, its session identity/lifecycle supplies ``session_id``
(and may key the subject) here — *without* changing :attr:`storage_key`, which is
subject-scoped so profiles already survive across sessions. Nothing in this
package invents F14's session machinery; it only consumes an opaque id string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pirn.core.pirn_opaque_value import PirnOpaqueValue

ProfileNamespace = Literal["user", "entity"]


@dataclass(frozen=True)
class ProfileKey(PirnOpaqueValue):
    """A subject-scoped, cross-session profile key.

    Attributes
    ----------
    namespace:
        Either ``"user"`` or ``"entity"``.
    subject_id:
        Non-empty stable id of the user or entity the profile describes.
    session_id:
        Optional originating-session id (the F14 seam); advisory only — it never
        enters :attr:`storage_key`, so profiles are shared across sessions.
    """

    namespace: ProfileNamespace
    subject_id: str
    session_id: str | None = None

    def __post_init__(self) -> None:
        if self.namespace not in ("user", "entity"):
            raise ValueError(
                f"ProfileKey: namespace must be 'user' or 'entity', got {self.namespace!r}"
            )
        if not isinstance(self.subject_id, str) or not self.subject_id:
            raise TypeError("ProfileKey: subject_id must be a non-empty str")
        if self.session_id is not None and not isinstance(self.session_id, str):
            raise TypeError("ProfileKey: session_id must be a str or None")

    @property
    def storage_key(self) -> str:
        """Return the deterministic, session-independent store key for this subject."""
        return f"profile:{self.namespace}:{self.subject_id}"

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "subject_id": self.subject_id,
            "session_id": self.session_id,
        }
