"""Tests for :class:`RouterRagPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.route_table import RouteTable
from pirn_agents.specializations.rag.router_rag_pipeline import RouterRagPipeline
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider, StubMemoryStore


class TestRouterRagPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_routes_and_synthesizes(self) -> None:
        docs = StubMemoryStore([{"id": "d1", "text": "doc hit"}])
        code = StubMemoryStore([{"id": "c1", "text": "code hit"}])
        table = RouteTable({"docs": docs, "code": code})
        llm = StubLLMProvider(["code", "routed answer"])
        with Tapestry() as t:
            RouterRagPipeline(
                query="how do I call the api",
                routes=table,
                llm=llm,
                top_k=3,
                _config=KnotConfig(id="router"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        response = result.outputs["router"]
        assert isinstance(response, AgentResponse)
        assert response.content == "routed answer"
        assert code.search_queries == ["how do I call the api"]
        assert docs.search_queries == []

    def test_rejects_non_route_table(self) -> None:
        with self.assertRaises(TypeError):
            RouterRagPipeline(
                query="q",
                routes="nope",  # type: ignore[arg-type]
                llm=StubLLMProvider(["docs", "a"]),
                _config=KnotConfig(id="router"),
            )
