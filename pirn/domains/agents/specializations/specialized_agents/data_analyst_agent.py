"""``DataAnalystAgent`` — SQL agent followed by LLM analysis.

A :class:`SubTapestry` that runs a :class:`SQLAgent` to fetch rows for a
natural-language question, then asks the LLM to write a short analysis
of those rows. The final :class:`AgentResponse` carries both the SQL
result block and the analysis text.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.specialized_agents._analysis_step import (
    _AnalysisStep,
)
from pirn.domains.agents.specializations.specialized_agents.sql_agent import (
    SQLAgent,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class DataAnalystAgent(SubTapestry):
    """Run :class:`SQLAgent` then analyse the rows; returns :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        question: Knot | str,
        llm: LLMProvider,
        pool: DatabaseConnectionPool,
        _config: KnotConfig,
        schema_description: str = "",
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "DataAnalystAgent: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "DataAnalystAgent: pool must be a DatabaseConnectionPool, "
                f"got {type(pool).__name__}"
            )
        if not isinstance(schema_description, str):
            raise TypeError(
                "DataAnalystAgent: schema_description must be a string, "
                f"got {type(schema_description).__name__}"
            )
        self._llm = llm
        self._pool = pool
        self._schema_description = schema_description
        super().__init__(question=question, _config=_config, **kwargs)

    async def process(self, question: str, **_: Any) -> AgentResponse:
        if not isinstance(question, str) or not question:
            raise TypeError(
                "DataAnalystAgent: question must be a non-empty string, "
                f"got {question!r}"
            )
        with Tapestry() as inner:
            sql_response = SQLAgent(
                question=question,
                llm=self._llm,
                pool=self._pool,
                schema_description=self._schema_description,
                _config=KnotConfig(id="sql_agent"),
            )
            _AnalysisStep(
                question=question,
                sql_response=sql_response,
                llm=self._llm,
                _config=KnotConfig(id="analyse"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("analyse")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
