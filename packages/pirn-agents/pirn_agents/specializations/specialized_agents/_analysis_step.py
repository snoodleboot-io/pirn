"""``_AnalysisStep`` — internal helper Knot for :class:`DataAnalystAgent`.

Sends a SQL result block plus the original question to the LLM for a
narrative analysis and combines the analysis with the SQL block into a
final :class:`AgentResponse`. Internal API.

Algorithm:
    1. Receive the original natural-language ``question`` and the
       ``sql_response`` :class:`AgentResponse` produced by the SQL agent.
    2. Build a two-message chat prompt: a system message that instructs
       the LLM to act as a data analyst, and a user message containing
       the question and the SQL result block.
    3. Send the prompt to the LLM via :meth:`LLMProvider.chat` and
       extract the text from the raw response.
    4. Concatenate the original SQL result block with the LLM analysis
       under an ``Analysis:`` header and return a new :class:`AgentResponse`.

Math:
    No numeric computation. The final string is a simple concatenation.

References:
    - ReAct-style two-pass agents: Yao et al., 2022 (arXiv 2210.03629).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.types.agent_response import AgentResponse


class _AnalysisStep(Knot):
    """Send the SQL result to the LLM for narrative analysis."""

    def __init__(
        self,
        *,
        question: Knot | str,
        sql_response: Knot | AgentResponse,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            question=question,
            sql_response=sql_response,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        question: str,
        sql_response: AgentResponse,
        llm: LLMProvider,
        **_: Any,
    ) -> AgentResponse:
        """Ask the LLM to analyse the SQL result and return a response combining both.

        Args:
            question: The original natural-language question answered by the SQL agent.
            sql_response: The AgentResponse containing the SQL query and result rows.
            llm: The LLM provider used to generate the narrative analysis.

        Returns:
            An AgentResponse whose content combines the SQL result block with the LLM analysis.

        Raises:
            TypeError: If sql_response is not an AgentResponse instance.
        """
        if not isinstance(sql_response, AgentResponse):
            raise TypeError(
                "DataAnalystAgent: sql_response must be an AgentResponse, "
                f"got {type(sql_response).__name__}"
            )
        chat_messages = [
            {
                "role": "system",
                "content": (
                    "You are a data analyst. Given a SQL result block, "
                    "write a concise analysis (3-5 sentences) that answers "
                    "the user's question and highlights notable trends."
                ),
            },
            {
                "role": "user",
                "content": (f"Question: {question}\n\nSQL result:\n{sql_response.content}"),
            },
        ]
        raw = await llm.chat(chat_messages)
        analysis = _AnalysisStep._extract_text(raw)
        combined = f"{sql_response.content}\n\nAnalysis:\n{analysis}"
        return AgentResponse(content=combined, finish_reason="stop")

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
