"""Tests for the three agent-domain interfaces.

Each interface raises :class:`NotImplementedError` from every method
when not overridden. This file pins those contracts.
"""

from __future__ import annotations

import pytest

from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.tool import Tool


@pytest.mark.asyncio
class TestLLMProviderInterface:
    async def test_chat_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="chat"):
            await LLMProvider().chat(messages=())

    async def test_stream_chat_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="stream_chat"):
            await LLMProvider().stream_chat(messages=())

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await LLMProvider().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyProvider(LLMProvider):
            pass

        with pytest.raises(NotImplementedError, match="MyProvider"):
            await MyProvider().chat(messages=())


@pytest.mark.asyncio
class TestMemoryStoreInterface:
    async def test_store_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="store"):
            await MemoryStore().store("k", {"a": 1})

    async def test_retrieve_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="retrieve"):
            await MemoryStore().retrieve("k")

    async def test_search_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="search"):
            await MemoryStore().search("q")

    async def test_forget_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="forget"):
            await MemoryStore().forget("k")

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await MemoryStore().close()


class TestToolInterfaceProperties:
    def test_name_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="name"):
            _ = Tool().name

    def test_description_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="description"):
            _ = Tool().description

    def test_parameters_schema_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="parameters_schema"):
            _ = Tool().parameters_schema


@pytest.mark.asyncio
class TestToolInterfaceInvoke:
    async def test_invoke_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="invoke"):
            await Tool().invoke({})
