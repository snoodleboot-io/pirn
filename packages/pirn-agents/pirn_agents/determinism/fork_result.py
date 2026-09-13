"""``ForkResult`` — the outcome of forking a run chain at a recorded point."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class ForkResult(PirnOpaqueValue):
    """The new run produced by :meth:`CheckpointForker.fork`, plus its provenance.

    ADR "agents speaks core" WS3 part 3: a fork is a branch of the session
    chain, not a persisted checkpoint — ``result`` is already durably
    recorded by ``RunHistory``/``DataStore`` (the engine does that
    unconditionally), so this value is a report, not a storage format; it has
    no ``to_payload``/``from_payload``.

    Attributes
    ----------
    new_run_id:
        ``run_id`` of the forked (new) run.
    source_run_id:
        ``run_id`` the fork branched from.
    forked_from_output_hash:
        Content hash of the source knot's output the fork point was taken at
        (the same shape :class:`~pirn_agents.sessions.resume_token.ResumeToken`
        uses).
    result:
        The forked run's ``RunResult``.
    """

    def __init__(
        self,
        *,
        new_run_id: str,
        source_run_id: str,
        forked_from_output_hash: str,
        result: RunResult,
    ) -> None:
        if not isinstance(new_run_id, str) or not new_run_id:
            raise TypeError("ForkResult: new_run_id must be a non-empty str")
        if not isinstance(source_run_id, str) or not source_run_id:
            raise TypeError("ForkResult: source_run_id must be a non-empty str")
        if not isinstance(forked_from_output_hash, str) or not forked_from_output_hash:
            raise TypeError("ForkResult: forked_from_output_hash must be a non-empty str")
        self._new_run_id = new_run_id
        self._source_run_id = source_run_id
        self._forked_from_output_hash = forked_from_output_hash
        self._result = result

    @property
    def new_run_id(self) -> str:
        return self._new_run_id

    @property
    def source_run_id(self) -> str:
        return self._source_run_id

    @property
    def forked_from_output_hash(self) -> str:
        return self._forked_from_output_hash

    @property
    def result(self) -> RunResult:
        return self._result

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "new_run_id": self._new_run_id,
            "source_run_id": self._source_run_id,
            "forked_from_output_hash": self._forked_from_output_hash,
        }
