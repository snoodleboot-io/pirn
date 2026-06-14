"""Tests for the three agent-domain interfaces.

Each interface raises :class:`NotImplementedError` from every method
when not overridden. This file pins those contracts.
"""

from __future__ import annotations

import unittest

from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.tool import Tool


class TestLLMProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_chat_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "chat"):
            await LLMProvider().chat(messages=())

    async def test_stream_chat_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "stream_chat"):
            await LLMProvider().stream_chat(messages=())

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await LLMProvider().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyProvider(LLMProvider):
            pass

        with self.assertRaisesRegex(NotImplementedError, "MyProvider"):
            await MyProvider().chat(messages=())


class TestMemoryStoreInterface(unittest.IsolatedAsyncioTestCase):
    async def test_store_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "store"):
            await MemoryStore().store("k", {"a": 1})

    async def test_retrieve_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "retrieve"):
            await MemoryStore().retrieve("k")

    async def test_search_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "search"):
            await MemoryStore().search("q")

    async def test_forget_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "forget"):
            await MemoryStore().forget("k")

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await MemoryStore().close()


class TestToolInterfaceProperties(unittest.TestCase):
    def test_name_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "name"):
            _ = Tool().name

    def test_description_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "description"):
            _ = Tool().description

    def test_parameters_schema_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "parameters_schema"):
            _ = Tool().parameters_schema


class TestToolInterfaceInvoke(unittest.IsolatedAsyncioTestCase):
    async def test_invoke_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "invoke"):
            await Tool().invoke({})
