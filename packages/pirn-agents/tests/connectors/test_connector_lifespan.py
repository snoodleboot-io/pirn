"""Unit tests for :meth:`~pirn_agents.connectors.connector_lifespan.ConnectorLifespan.manage` deterministic teardown (F16-S5)."""

from __future__ import annotations

import asyncio

import pytest

from pirn_agents.connectors.connector_lifespan import ConnectorLifespan


class _AsyncClosable:
    def __init__(self, log: list[str], name: str) -> None:
        self._log = log
        self._name = name

    async def close(self) -> None:
        self._log.append(self._name)


class _SyncClosable:
    def __init__(self, log: list[str], name: str) -> None:
        self._log = log
        self._name = name

    def close(self) -> None:
        self._log.append(self._name)


class TestConnectorLifespan:
    async def test_yields_connectors(self) -> None:
        log: list[str] = []
        a = _AsyncClosable(log, "a")
        async with ConnectorLifespan.manage(a) as vended:
            assert vended == (a,)

    async def test_closes_all_in_reverse_order_on_success(self) -> None:
        log: list[str] = []
        a = _AsyncClosable(log, "a")
        b = _SyncClosable(log, "b")
        async with ConnectorLifespan.manage(a, b):
            pass
        assert log == ["b", "a"]

    async def test_closes_all_even_when_body_raises(self) -> None:
        log: list[str] = []
        a = _AsyncClosable(log, "a")
        b = _AsyncClosable(log, "b")
        with pytest.raises(RuntimeError, match="boom"):
            async with ConnectorLifespan.manage(a, b):
                raise RuntimeError("boom")
        assert log == ["b", "a"]

    async def test_ignores_objects_without_close(self) -> None:
        log: list[str] = []
        a = _AsyncClosable(log, "a")
        async with ConnectorLifespan.manage(object(), a):
            pass
        assert log == ["a"]

    async def test_closes_all_connectors_even_if_one_close_fails(self) -> None:
        log: list[str] = []

        class _Failing:
            async def close(self) -> None:
                raise ValueError("close failed")

        a = _AsyncClosable(log, "a")
        failing = _Failing()
        with pytest.raises(ValueError, match="close failed"):
            async with ConnectorLifespan.manage(a, failing):
                pass
        # 'a' still closed even though the later-constructed 'failing' raised.
        assert log == ["a"]


class _Failing:
    """A connector whose ``close`` raises the error it was built with."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def close(self) -> None:
        raise self._error


class TestCloseFailuresAreReportedInFull:
    """PIR-873: ``raise errors[0]`` dropped the rest and replaced the body's error."""

    async def test_every_close_failure_is_reported_not_just_the_first(self) -> None:
        # Arrange — two connectors that both fail to close.
        first = _Failing(ValueError("first failed"))
        second = _Failing(TypeError("second failed"))

        # Act / Assert
        with pytest.raises(ExceptionGroup) as caught:
            async with ConnectorLifespan.manage(first, second):
                pass
        messages = [str(exc) for exc in caught.value.exceptions]
        assert sorted(messages) == ["first failed", "second failed"]

    async def test_a_single_close_failure_is_still_raised_as_itself(self) -> None:
        with pytest.raises(ValueError, match="only failure"):
            async with ConnectorLifespan.manage(_Failing(ValueError("only failure"))):
                pass

    async def test_the_bodys_exception_wins_over_a_close_failure(self) -> None:
        # Arrange
        log: list[str] = []
        good = _AsyncClosable(log, "good")
        failing = _Failing(ValueError("close failed"))

        # Act / Assert — the caller's own failure, not the teardown's.
        with pytest.raises(RuntimeError, match="body boom") as caught:
            async with ConnectorLifespan.manage(good, failing):
                raise RuntimeError("body boom")

        # And the close failure is not lost: it rides along as a note.
        notes = getattr(caught.value, "__notes__", [])
        assert any("close failed" in note for note in notes)
        assert log == ["good"]

    async def test_every_close_failure_is_noted_on_the_bodys_exception(self) -> None:
        with pytest.raises(RuntimeError) as caught:
            async with ConnectorLifespan.manage(
                _Failing(ValueError("first failed")), _Failing(TypeError("second failed"))
            ):
                raise RuntimeError("body boom")
        notes = " ".join(getattr(caught.value, "__notes__", []))
        assert "first failed" in notes
        assert "second failed" in notes

    async def test_a_cancellation_during_close_is_not_collected_as_a_close_error(self) -> None:
        # Arrange — teardown used to catch BaseException and re-raise it as a
        # connector fault; a cancellation must propagate as itself.
        class _Cancelling:
            async def close(self) -> None:
                raise asyncio.CancelledError

        # Act / Assert
        with pytest.raises(asyncio.CancelledError):
            async with ConnectorLifespan.manage(_Cancelling()):
                pass
