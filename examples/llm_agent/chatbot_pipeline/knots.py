"""Knot factories for the ``examples.llm_agent.chatbot_pipeline`` example."""

from __future__ import annotations

import asyncio
import json

from pirn.core.knot_factory import KnotFactory

from examples.llm_agent.chatbot_pipeline.entities import Entities
from examples.llm_agent.chatbot_pipeline.fake_llm_client import FakeLLMClient
from examples.llm_agent.chatbot_pipeline.generated_response import GeneratedResponse
from examples.llm_agent.chatbot_pipeline.intent import Intent
from examples.llm_agent.chatbot_pipeline.parsed_message import ParsedMessage
from examples.llm_agent.chatbot_pipeline.post_processed_response import PostProcessedResponse
from examples.llm_agent.chatbot_pipeline.retrieved_context import RetrievedContext
from examples.llm_agent.chatbot_pipeline.safety_result import SafetyResult
from examples.llm_agent.chatbot_pipeline.turn_log import TurnLog


@KnotFactory.knot
async def parse_message(
    message_text: str,
    user_id: str,
    session_id: str,
    turn_number: int,
) -> ParsedMessage:
    """Normalise the incoming message."""
    return ParsedMessage(
        text=message_text.strip(),
        user_id=user_id,
        session_id=session_id,
        turn_number=turn_number,
    )


@KnotFactory.knot
async def classify_intent(parsed: ParsedMessage) -> Intent:
    """Classify the user's intent using a fast LLM call."""
    response = await FakeLLMClient.call(
        system="Classify intent. Return JSON: {label, confidence}",
        user=parsed.text,
        max_tokens=50,
    )
    data = json.loads(response["content"])
    return Intent(label=data["label"], confidence=data["confidence"])


@KnotFactory.knot
async def extract_entities(parsed: ParsedMessage) -> Entities:
    """Extract named entities from the message."""
    response = await FakeLLMClient.call(
        system="Extract entities. Return JSON array: [{type, value}]",
        user=parsed.text,
        max_tokens=100,
    )
    items = json.loads(response["content"])
    return Entities(items=items)


@KnotFactory.knot
async def retrieve_context(
    parsed: ParsedMessage,
    intent: Intent,
    entities: Entities,
) -> RetrievedContext:
    """Retrieve relevant knowledge-base chunks (RAG)."""
    if intent.label == "chitchat":
        return RetrievedContext(chunks=[], source_ids=[])

    query = f"{parsed.text} " + " ".join(e["value"] for e in entities.items)
    response = await FakeLLMClient.call(
        system="Retrieve relevant context for this query.",
        user=query,
        max_tokens=300,
    )
    return RetrievedContext(
        chunks=[response["content"]],
        source_ids=["kb_001"],
    )


@KnotFactory.knot
async def check_safety(parsed: ParsedMessage) -> SafetyResult:
    """Run a safety / moderation check on the user message."""
    await asyncio.sleep(0.01)
    blocked_patterns = ["ignore previous", "jailbreak", "pretend you are"]
    text_lower = parsed.text.lower()
    for pattern in blocked_patterns:
        if pattern in text_lower:
            return SafetyResult(safe=False, reason=f"Blocked pattern: '{pattern}'")
    return SafetyResult(safe=True)


@KnotFactory.knot
async def generate_response(
    parsed: ParsedMessage,
    context: RetrievedContext,
    safety: SafetyResult,
    conversation_history: str,
) -> GeneratedResponse:
    """Generate the assistant response with the LLM.

    Raises PermissionError if the safety check failed — downstream knots skip.
    """
    if not safety.safe:
        raise PermissionError(f"Safety block: {safety.reason}")

    context_block = "\n".join(context.chunks) if context.chunks else "No specific context."
    system_prompt = f"""You are a helpful customer support assistant.

Relevant context:
{context_block}

Answer concisely and accurately."""

    user_prompt = f"{conversation_history}\nUser: {parsed.text}"
    response = await FakeLLMClient.call(system=system_prompt, user=user_prompt, max_tokens=500)
    return GeneratedResponse(
        text=response["content"],
        model=response.get("model", "claude-sonnet-4-6"),
        tokens_used=(
            response.get("usage", {}).get("input_tokens", 0)
            + response.get("usage", {}).get("output_tokens", 0)
        ),
        finish_reason=response.get("stop_reason", "end_turn"),
    )


@KnotFactory.knot
async def post_process(
    response: GeneratedResponse,
    context: RetrievedContext,
) -> PostProcessedResponse:
    """Append source citations and apply output formatting."""
    text = response.text
    citations = context.source_ids
    if citations:
        text += f"\n\n*Sources: {', '.join(citations)}*"
    return PostProcessedResponse(text=text, citations=citations)


@KnotFactory.knot
async def log_turn(
    parsed: ParsedMessage,
    intent: Intent,
    safety: SafetyResult,
    response: GeneratedResponse,
) -> TurnLog:
    """Persist structured turn metadata for analytics and debugging."""
    await asyncio.sleep(0.002)
    return TurnLog(
        user_id=parsed.user_id,
        session_id=parsed.session_id,
        turn=parsed.turn_number,
        intent=intent.label,
        safe=safety.safe,
        response_length=len(response.text),
    )
