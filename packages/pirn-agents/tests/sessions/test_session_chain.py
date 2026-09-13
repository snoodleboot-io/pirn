"""Unit tests for :class:`SessionChain` and :meth:`RunState.from_chain`.

Exercises real ``Tapestry.run()`` calls chained via ``_parent_run_id`` — the
actual mechanism ADR "agents speaks core" WS3 part 2 uses for a session — over
an ``InMemoryHistory``, rather than hand-building ``RunResult``s.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

from pirn_agents.sessions.run_state import RunState
from pirn_agents.sessions.session_chain import SESSION_ID_PARAMETER, SessionChain
from pirn_agents.sessions.session_message import SessionMessage


class _MessageSource(Source):
    """Test turn knot: returns a canned session message under a fixed id."""

    def __init__(self, *, message: SessionMessage, _config: KnotConfig) -> None:
        super().__init__(_config=_config)
        self._mutable_message = message

    async def process(self, **_: Any) -> SessionMessage:
        return self._mutable_message


async def _run_turn(
    history: InMemoryHistory, *, session_id: str, previous_run_id: str | None, text: str
):
    message = SessionMessage(role="user", content=text)
    with Tapestry(history=history) as tapestry:
        _MessageSource(message=message, _config=KnotConfig(id="session_message"))
        result = await SessionChain.run_turn(
            tapestry,
            RunRequest(),
            session_id=session_id,
            previous_run_id=previous_run_id,
        )
    assert result.succeeded
    return result


class TestSessionChainRunTurn:
    async def test_stamps_session_id_into_a_declared_parameter(self) -> None:
        history = InMemoryHistory()
        with Tapestry(history=history) as tapestry:
            Parameter(name=SESSION_ID_PARAMETER, type_=str)
            _MessageSource(
                message=SessionMessage(role="user", content="hi"),
                _config=KnotConfig(id="session_message"),
            )
            result = await SessionChain.run_turn(
                tapestry, RunRequest(), session_id="s1", previous_run_id=None
            )
        assert result.succeeded
        assert result.outputs[f"param:{SESSION_ID_PARAMETER}"] == "s1"

    async def test_first_turn_has_no_parent(self) -> None:
        history = InMemoryHistory()
        result = await _run_turn(history, session_id="s1", previous_run_id=None, text="hi")
        assert result.parent_run_id is None
        assert result.parent_knot_id is None

    async def test_second_turn_chains_to_the_first(self) -> None:
        history = InMemoryHistory()
        first = await _run_turn(history, session_id="s1", previous_run_id=None, text="hi")
        second = await _run_turn(
            history, session_id="s1", previous_run_id=first.run_id, text="hello again"
        )
        assert second.parent_run_id == first.run_id
        assert second.parent_knot_id is None

    async def test_rejects_empty_session_id(self) -> None:
        history = InMemoryHistory()
        with Tapestry(history=history) as tapestry:
            _MessageSource(
                message=SessionMessage(role="user", content="hi"),
                _config=KnotConfig(id="session_message"),
            )
            try:
                await SessionChain.run_turn(
                    tapestry, RunRequest(), session_id="", previous_run_id=None
                )
            except ValueError:
                pass
            else:
                raise AssertionError("expected ValueError")


class TestSessionChainTurnsOf:
    async def test_returns_the_whole_chain_in_order(self) -> None:
        history = InMemoryHistory()
        first = await _run_turn(history, session_id="s1", previous_run_id=None, text="one")
        second = await _run_turn(history, session_id="s1", previous_run_id=first.run_id, text="two")
        third = await _run_turn(
            history, session_id="s1", previous_run_id=second.run_id, text="three"
        )

        chain = await SessionChain.turns_of(history, first.run_id)

        assert [run.run_id for run in chain] == [first.run_id, second.run_id, third.run_id]

    async def test_single_turn_session_is_a_chain_of_one(self) -> None:
        history = InMemoryHistory()
        first = await _run_turn(history, session_id="s1", previous_run_id=None, text="only")
        chain = await SessionChain.turns_of(history, first.run_id)
        assert [run.run_id for run in chain] == [first.run_id]

    async def test_unknown_root_raises_key_error(self) -> None:
        history = InMemoryHistory()
        try:
            await SessionChain.turns_of(history, "no-such-run")
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError")


class TestRunStateFromChain:
    async def test_projects_messages_and_last_run_id(self) -> None:
        history = InMemoryHistory()
        first = await _run_turn(history, session_id="s1", previous_run_id=None, text="one")
        second = await _run_turn(history, session_id="s1", previous_run_id=first.run_id, text="two")

        chain = await SessionChain.turns_of(history, first.run_id)
        state = RunState.from_chain(session_id="s1", turns=chain)

        assert [m.content for m in state.messages] == ["one", "two"]
        assert state.last_run_id == second.run_id
        assert state.cursor.completed_steps == (first.run_id, second.run_id)

    def test_empty_chain_projects_an_empty_state(self) -> None:
        state = RunState.from_chain(session_id="s1", turns=[])
        assert state.messages == ()
        assert state.last_run_id is None

    def test_turn_missing_the_message_key_contributes_nothing(self) -> None:
        now = datetime.now(UTC)
        turn = RunResult(
            run_id="run-1",
            terminals_requested=[],
            outputs={},
            started_at=now,
            finished_at=now,
            dispatcher="LocalDispatcher",
            parent_run_id=None,
            parent_knot_id=None,
            actor=None,
            trigger=None,
        )
        state = RunState.from_chain(session_id="s1", turns=[turn])
        assert state.messages == ()
        assert state.last_run_id == "run-1"
