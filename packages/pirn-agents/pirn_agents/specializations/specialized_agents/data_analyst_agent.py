"""``DataAnalystAgent`` — SQL agent followed by LLM analysis.

A :class:`SubTapestry` that runs a :class:`SQLAgent` to fetch rows for a
natural-language question, then asks the LLM to write a short analysis
of those rows. The final :class:`AgentResponse` carries both the SQL
result block and the analysis text.

Algorithm:
    1. Receive ``question`` (str), ``llm``, ``pool``, and
       ``schema_description`` as plain values.
    2. Validate that ``question`` is a non-empty string.
    3. Build an inner :class:`Tapestry` containing :class:`SQLAgent` and
       :class:`_AnalysisStep`.
    4. Run the inner tapestry and extract the ``AgentResponse`` output.

Math:
    None.

References:
    None.
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.specialized_agents._analysis_step import (
    _AnalysisStep,
)
from pirn_agents.specializations.specialized_agents.sql_agent import (
    SQLAgent,
)


class DataAnalystAgent(SubTapestry):
    """Run :class:`SQLAgent` then analyse the rows; returns :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        question: Knot | str,
        llm: Knot | LLMProvider,
        pool: Knot | DatabaseConnectionPool,
        _config: KnotConfig,
        schema_description: Knot | str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            question=question,
            llm=llm,
            pool=pool,
            schema_description=schema_description,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        question: str,
        llm: LLMProvider,
        pool: DatabaseConnectionPool,
        schema_description: str = "",
        **_: Any,
    ) -> Any:
        """Run the SQL agent on the question, analyse the rows via the LLM, and return the combined response.

        Args:
            question: The non-empty natural-language question to answer with SQL and LLM analysis.
            llm: The LLM provider used for SQL generation and analysis.
            pool: The database connection pool used for SQL execution.
            schema_description: Optional schema hint passed to the SQL agent.

        Returns:
            An AgentResponse combining the SQL result block with a narrative analysis.

        Raises:
            TypeError: If question is not a non-empty string, llm is not an LLMProvider,
                pool is not a DatabaseConnectionPool, or schema_description is not a string.
        """
        if not isinstance(question, str) or not question:
            raise TypeError(
                f"DataAnalystAgent: question must be a non-empty string, got {question!r}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"DataAnalystAgent: llm must be an LLMProvider, got {type(llm).__name__}"
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
        sql_response = SQLAgent(
            question=question,
            llm=llm,
            pool=pool,
            schema_description=schema_description,
            _config=KnotConfig(id="sql_agent"),
        )
        return _AnalysisStep(
            question=question,
            sql_response=sql_response,
            llm=llm,
            _config=KnotConfig(id="analyse"),
        )
