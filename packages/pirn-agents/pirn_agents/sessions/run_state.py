"""``RunState`` — the read-model projected from a session's run chain.

ADR "agents speaks core" WS3 part 2. Before this, ``RunState`` was itself the
persisted checkpoint blob, written wholesale into a
:class:`~pirn_agents.sessions.session_store.SessionStore` (see
:class:`~pirn_agents.sessions.run_checkpoint.RunCheckpoint`, now a deprecated
compatibility shim). Nothing persists a ``RunState`` as the source of truth
any more: the engine already durably records every turn's ``RunResult`` via
``RunHistory``/``DataStore``, and :meth:`from_chain` rebuilds this value on
demand from a session's chain of turns
(:class:`~pirn_agents.sessions.session_chain.SessionChain`). ``RunState``
itself, :meth:`to_payload`, and :meth:`from_payload` are unchanged — it is
still the convenient, JSON-friendly read model callers work with (an API
response, a debugging snapshot) — the only thing that moved is where it comes
from.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.sessions.execution_cursor import ExecutionCursor
from pirn_agents.sessions.session_message import SessionMessage
from pirn_agents.sessions.session_tool_result import SessionToolResult

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult

#: Default RunResult.outputs key a turn's message-producing knot is expected
#: to use, read by :meth:`RunState.from_chain`.
DEFAULT_MESSAGE_OUTPUT_KEY = "session_message"
#: Default RunResult.outputs key a turn's tool-result-producing knot is
#: expected to use, read by :meth:`RunState.from_chain`.
DEFAULT_TOOL_RESULT_OUTPUT_KEY = "session_tool_result"
#: Default RunResult.outputs key a turn's plan-step-producing knot is
#: expected to use, read by :meth:`RunState.from_chain`.
DEFAULT_PLAN_STEP_OUTPUT_KEY = "session_plan_step"


@dataclass(frozen=True)
class RunState(PirnOpaqueValue):
    """A round-trippable read model: messages, plan, tool results, cursor.

    The value is keyed by ``session_id`` and carries everything a caller needs
    to see where a session stands: the ``messages`` accumulated so far, the
    ordered ``plan`` steps, the ``tool_results`` produced, and the
    :class:`ExecutionCursor` marking how far the plan has been executed. It
    round-trips through :meth:`to_payload` / :meth:`from_payload` with no data
    loss, but see the module docstring — nothing persists it as the source of
    truth any more.

    Attributes
    ----------
    session_id:
        Stable id keying this session.
    messages:
        The ordered message history.
    plan:
        The ordered plan step labels.
    tool_results:
        The tool results produced so far.
    cursor:
        The execution cursor. When built by :meth:`from_chain`,
        ``completed_steps`` holds each turn's ``run_id`` in order, so
        ``completed_steps[-1]`` (exposed as :attr:`last_run_id`) is the run to
        resume from.
    """

    session_id: str
    messages: tuple[SessionMessage, ...] = field(default_factory=tuple)
    plan: tuple[str, ...] = field(default_factory=tuple)
    tool_results: tuple[SessionToolResult, ...] = field(default_factory=tuple)
    cursor: ExecutionCursor = field(default_factory=ExecutionCursor)

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise TypeError("RunState: session_id must be a non-empty str")
        if not isinstance(self.cursor, ExecutionCursor):
            raise TypeError(
                f"RunState: cursor must be an ExecutionCursor, got {type(self.cursor).__name__}"
            )

    def remaining_plan(self) -> tuple[str, ...]:
        """Return the uncomputed tail of the plan (steps past the cursor)."""
        return self.plan[self.cursor.step_index :]

    @property
    def last_run_id(self) -> str | None:
        """The most recently completed turn's ``run_id``, or ``None``.

        Only meaningful for a state built by :meth:`from_chain`, where
        ``cursor.completed_steps`` holds run ids; a state built any other way
        (e.g. directly, or via :meth:`from_payload`) has whatever
        ``completed_steps`` its caller gave it.
        """
        return self.cursor.completed_steps[-1] if self.cursor.completed_steps else None

    @classmethod
    def from_chain(
        cls,
        *,
        session_id: str,
        turns: Sequence[RunResult],
        message_output_key: str = DEFAULT_MESSAGE_OUTPUT_KEY,
        tool_result_output_key: str = DEFAULT_TOOL_RESULT_OUTPUT_KEY,
        plan_step_output_key: str = DEFAULT_PLAN_STEP_OUTPUT_KEY,
    ) -> RunState:
        """Project a ``RunState`` from a session's chain of turn ``RunResult``s.

        Each turn contributes to the projection through well-known
        ``RunResult.outputs`` keys (the ids of the knots a turn's pipeline is
        expected to terminate on): a :class:`SessionMessage` under
        ``message_output_key``, a :class:`SessionToolResult` under
        ``tool_result_output_key``, and a plan-step label (``str``) under
        ``plan_step_output_key``. A turn missing one of these — or whose value
        under that key is the wrong type — simply contributes nothing for it;
        this projection never raises for a pipeline shape it does not
        recognise.

        Args:
            session_id: The session these turns belong to.
            turns: The chain's ``RunResult``s, oldest first — see
                :meth:`~pirn_agents.sessions.session_chain.SessionChain.turns_of`.
            message_output_key: The output key a turn's message knot uses.
            tool_result_output_key: The output key a turn's tool-result knot
                uses.
            plan_step_output_key: The output key a turn's plan-step knot uses.

        Returns:
            The projected ``RunState``, with ``cursor.completed_steps`` set to
            each turn's ``run_id`` in order.
        """
        messages: list[SessionMessage] = []
        tool_results: list[SessionToolResult] = []
        plan: list[str] = []
        completed_run_ids: list[str] = []
        for turn in turns:
            message = turn.outputs.get(message_output_key)
            if isinstance(message, SessionMessage):
                messages.append(message)
            tool_result = turn.outputs.get(tool_result_output_key)
            if isinstance(tool_result, SessionToolResult):
                tool_results.append(tool_result)
            plan_step = turn.outputs.get(plan_step_output_key)
            if isinstance(plan_step, str):
                plan.append(plan_step)
            completed_run_ids.append(turn.run_id)
        cursor = ExecutionCursor(
            # step_index counts completed *plan* steps, so remaining_plan()
            # still indexes correctly; completed_steps holds run ids (one per
            # turn, not one per plan step) so last_run_id can read the tail —
            # the two fields intentionally diverge here.
            step_index=len(plan),
            completed_steps=tuple(completed_run_ids),
        )
        return cls(
            session_id=session_id,
            messages=tuple(messages),
            plan=tuple(plan),
            tool_results=tuple(tool_results),
            cursor=cursor,
        )

    def with_message(self, message: SessionMessage) -> RunState:
        """Return a new state with ``message`` appended to the history."""
        return RunState(
            session_id=self.session_id,
            messages=(*self.messages, message),
            plan=self.plan,
            tool_results=self.tool_results,
            cursor=self.cursor,
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping capturing the whole run state."""
        return {
            "session_id": self.session_id,
            "messages": [m.to_payload() for m in self.messages],
            "plan": list(self.plan),
            "tool_results": [r.to_payload() for r in self.tool_results],
            "cursor": self.cursor.to_payload(),
        }

    @classmethod
    def from_payload(cls, payload: Any) -> RunState:
        """Reconstruct a run state from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"RunState.from_payload: payload must be a Mapping, got {type(payload).__name__}"
            )
        messages: Sequence[Any] = payload.get("messages", ())
        results: Sequence[Any] = payload.get("tool_results", ())
        plan: Sequence[Any] = payload.get("plan", ())
        return cls(
            session_id=str(payload["session_id"]),
            messages=tuple(SessionMessage.from_payload(m) for m in messages),
            plan=tuple(str(step) for step in plan),
            tool_results=tuple(SessionToolResult.from_payload(r) for r in results),
            cursor=ExecutionCursor.from_payload(payload.get("cursor", {})),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
