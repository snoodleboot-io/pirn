"""Unit tests for :func:`connector_lifespan` deterministic teardown (F16-S5)."""

from __future__ import annotations

import pytest

from pirn_agents.connector_lifespan import connector_lifespan


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
        async with connector_lifespan(a) as vended:
            assert vended == (a,)

    async def test_closes_all_in_reverse_order_on_success(self) -> None:
        log: list[str] = []
        a = _AsyncClosable(log, "a")
        b = _SyncClosable(log, "b")
        async with connector_lifespan(a, b):
            pass
        assert log == ["b", "a"]

    async def test_closes_all_even_when_body_raises(self) -> None:
        log: list[str] = []
        a = _AsyncClosable(log, "a")
        b = _AsyncClosable(log, "b")
        with pytest.raises(RuntimeError, match="boom"):
            async with connector_lifespan(a, b):
                raise RuntimeError("boom")
        assert log == ["b", "a"]

    async def test_ignores_objects_without_close(self) -> None:
        log: list[str] = []
        a = _AsyncClosable(log, "a")
        async with connector_lifespan(object(), a):
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
            async with connector_lifespan(a, failing):
                pass
        # 'a' still closed even though the later-constructed 'failing' raised.
        assert log == ["a"]
