"""Tests for the three agent-domain interfaces.

Each interface raises :class:`NotImplementedError` from every method
when not overridden. This file pins those contracts.
"""

from __future__ import annotations

import unittest

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.tools.tool import Tool


class TestLLMProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_chat_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "chat"):
            await LLMProvider().chat(messages=())

    async def test_stream_chat_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "stream_chat"):
            LLMProvider().stream_chat(messages=())

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
    def test_tool_is_a_knot_class(self) -> None:
        from pirn.core.knot import Knot

        self.assertTrue(issubclass(Tool, Knot))

    def test_declaration_of_the_bare_base_is_empty(self) -> None:
        declaration = Tool.declaration()
        self.assertEqual(declaration.name, "tool")
        self.assertEqual(declaration.parameters, {"type": "object", "properties": {}})


class TestToolInterfaceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_raises_not_implemented(self) -> None:
        from pirn.core.knot_config import KnotConfig
        from pirn.tapestry import Tapestry

        with Tapestry():
            bare = Tool(_config=KnotConfig(id="bare"))
        with self.assertRaisesRegex(NotImplementedError, "process"):
            await bare.process()
