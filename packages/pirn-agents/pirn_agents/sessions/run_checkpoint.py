"""``RunCheckpoint`` — a content-addressed, serialisable checkpoint of a run.

ADR "agents speaks core" WS3 part 2 deprecation candidate: the active session
model no longer persists a ``RunCheckpoint`` (see
:mod:`pirn_agents.sessions.session_chain` and the module docstring on
:mod:`pirn_agents.sessions.run_state`). This class stays for one cycle for any
already-persisted checkpoints and callers that have not migrated —
:meth:`create` and construction both emit ``DeprecationWarning``.

``format_version`` migration (sanctioned by the ADR, since the digest is a
persisted storage format —
see ``tests/sessions/test_checkpoint_hash_invariant.py``):

* **v1** (the original, and every checkpoint persisted before this version):
  ``CanonicalJson.digest(state.to_payload())`` — bare 64-hex SHA-256.
* **v2** (the new default): ``pirn.core.hashing.content_hash(state.to_payload())``
  — the one canonicaliser every other pirn domain's lineage/content hashing
  uses, ``"sha256:"``-prefixed.

:meth:`from_payload` defaults ``format_version`` to ``1`` when the field is
absent, so an already-persisted (pre-migration) payload keeps reading as v1
with no re-hash; :meth:`migrate_v1_to_v2` re-hashes an existing v1 checkpoint
into a fresh v2 one for a caller that wants to upgrade a stored checkpoint.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from pirn.core.hashing import content_hash
from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.serialization.canonical_json import CanonicalJson
from pirn_agents.sessions.run_state import RunState


@dataclass(frozen=True)
class RunCheckpoint(PirnOpaqueValue):
    """A :class:`RunState` tagged with a content-addressed id and format version.

    ``checkpoint_id`` is a content hash of the state's canonical JSON — see the
    module docstring for the v1/v2 digest difference — so two checkpoints of
    identical state (and the same ``format_version``) share an id, and any
    change to messages, plan, tool results, or cursor yields a different one.

    Attributes
    ----------
    checkpoint_id:
        Content-addressed digest of the canonical state payload.
    state:
        The captured :class:`RunState`.
    format_version:
        Which digest algorithm produced ``checkpoint_id`` — see the module
        docstring. Defaults to :data:`RunCheckpoint.current_format_version`.
    """

    #: Format versions :meth:`RunCheckpoint.content_hash` understands.
    _known_format_versions: ClassVar[tuple[int, ...]] = (1, 2)
    #: The version newly created checkpoints use.
    current_format_version: ClassVar[int] = 2

    checkpoint_id: str
    state: RunState
    format_version: int = current_format_version

    def __post_init__(self) -> None:
        if not isinstance(self.checkpoint_id, str) or not self.checkpoint_id:
            raise TypeError("RunCheckpoint: checkpoint_id must be a non-empty str")
        if not isinstance(self.state, RunState):
            raise TypeError(
                f"RunCheckpoint: state must be a RunState, got {type(self.state).__name__}"
            )
        if self.format_version not in RunCheckpoint._known_format_versions:
            raise ValueError(
                f"RunCheckpoint: format_version must be one of {RunCheckpoint._known_format_versions}, "
                f"got {self.format_version!r}"
            )
        warnings.warn(
            "RunCheckpoint is deprecated (ADR agents-speaks-core WS3): sessions "
            "are a chain of engine runs now — see pirn_agents.sessions.session_chain "
            "and pirn_agents.sessions.run_state.RunState.from_chain. Kept for "
            "reading/migrating already-persisted checkpoints.",
            DeprecationWarning,
            stacklevel=2,
        )

    @staticmethod
    def content_hash(state: RunState, *, format_version: int = current_format_version) -> str:
        """Return the digest of ``state``'s canonical JSON payload.

        Args:
            state: The state to digest.
            format_version: ``1`` for the original ``CanonicalJson.digest``
                form, ``2`` (the default) for core's ``content_hash``.

        Raises:
            TypeError: If the payload contains a value JSON cannot represent
                (``format_version=1``).
            ValueError: If ``format_version`` is not ``1`` or ``2``.
        """
        if format_version == 1:
            return CanonicalJson.digest(state.to_payload())
        if format_version == 2:
            return content_hash(state.to_payload())
        raise ValueError(
            f"RunCheckpoint.content_hash: format_version must be one of "
            f"{RunCheckpoint._known_format_versions}, got {format_version!r}"
        )

    @classmethod
    def create(
        cls, state: RunState, *, format_version: int = current_format_version
    ) -> RunCheckpoint:
        """Build a checkpoint whose id is the content hash of ``state``.

        Raises:
            TypeError: If ``state`` is not a RunState.
            ValueError: If ``format_version`` is not ``1`` or ``2``.
        """
        if not isinstance(state, RunState):
            raise TypeError(
                f"RunCheckpoint.create: state must be a RunState, got {type(state).__name__}"
            )
        return cls(
            checkpoint_id=cls.content_hash(state, format_version=format_version),
            state=state,
            format_version=format_version,
        )

    @classmethod
    def migrate_v1_to_v2(cls, checkpoint: RunCheckpoint) -> RunCheckpoint:
        """Return a fresh v2 checkpoint re-hashed from a v1 ``checkpoint``'s state.

        Args:
            checkpoint: A ``format_version=1`` checkpoint to migrate.

        Returns:
            A new ``format_version=2`` ``RunCheckpoint`` over the same state.
            ``checkpoint_id`` changes (the two digest algorithms differ); a
            caller re-keying storage must write the new id, not assume it
            matches the old one.

        Raises:
            TypeError: If ``checkpoint`` is not a ``RunCheckpoint``.
            ValueError: If ``checkpoint.format_version`` is not ``1``.
        """
        if not isinstance(checkpoint, RunCheckpoint):
            raise TypeError(
                f"RunCheckpoint.migrate_v1_to_v2: checkpoint must be a RunCheckpoint, "
                f"got {type(checkpoint).__name__}"
            )
        if checkpoint.format_version != 1:
            raise ValueError(
                f"RunCheckpoint.migrate_v1_to_v2: checkpoint is already "
                f"format_version {checkpoint.format_version}, not 1"
            )
        return cls.create(checkpoint.state, format_version=2)

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this checkpoint."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "state": self.state.to_payload(),
            "format_version": self.format_version,
        }

    @classmethod
    def from_payload(cls, payload: Any) -> RunCheckpoint:
        """Reconstruct a checkpoint from a mapping produced by :meth:`to_payload`.

        ``format_version`` defaults to ``1`` when absent, so a payload
        persisted before this field existed is read back as the legacy
        format rather than silently reinterpreted as v2.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"RunCheckpoint.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            checkpoint_id=str(payload["checkpoint_id"]),
            state=RunState.from_payload(payload["state"]),
            format_version=int(payload.get("format_version", 1)),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "state": self.state._pirn_audit_dict(),
            "format_version": self.format_version,
        }
