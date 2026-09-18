"""``FakeBackends`` — the simulated tool, MCP and sub-agent back-ends.

Part of the ``examples.llm_agent.agent_loop`` example.  Every method is a pure
function of its arguments and the deterministic RNG it is handed, so a session
replays identically for the same ``run_seed``.
"""

from __future__ import annotations

import random
from typing import ClassVar


class FakeBackends:
    """Stand-ins for the three action back-ends the session can reach."""

    _weather_conditions: ClassVar[tuple[str, ...]] = (
        "Clear",
        "Overcast",
        "Light rain",
        "Sunny",
        "Windy",
    )
    _kb_topics: ClassVar[dict[str, str]] = {
        "refund": "Refunds issued within 30 days. Digital goods non-refundable post-download.",
        "cancellation": "Cancel anytime; access continues to end of billing period.",
        "pricing": "Basic $9/mo · Pro $29/mo · Enterprise $99/mo.",
    }
    _email_tones: ClassVar[tuple[str, ...]] = ("professional", "empathetic", "concise")

    @classmethod
    def tool(cls, name: str, args: dict, rng: random.Random) -> str:
        """Run a local tool function (weather, calculator, file read)."""
        if name == "get_weather":
            loc = args.get("location", "unknown")
            temp = rng.randint(8, 28)
            cond = rng.choice(cls._weather_conditions)
            return f"{loc}: {cond}, {temp}°C"
        if name == "calculate":
            expr = args.get("expression", "0")
            try:
                return f"{expr} = {eval(expr, {'__builtins__': {}})}"
            except Exception:
                return f"could not evaluate: {expr}"
        if name == "read_file":
            n = rng.randint(1, 9)
            return f"[contents of {args.get('path', '?')}]: lorem ipsum policy text paragraph {n}"
        return f"[tool:{name}] ok"

    @classmethod
    def mcp(cls, name: str, args: dict, rng: random.Random) -> str:
        """Call a simulated remote MCP service (web search, knowledge base, fetch)."""
        if name == "web_search":
            q = args.get("query", "")
            snippets = [
                f"Recent study on '{q}' shows promising results in Q{rng.randint(1, 4)} 2025.",
                f"Experts disagree on {q}; {rng.randint(2, 8)} competing frameworks proposed.",
                f"'{q}' trend up {rng.randint(10, 80)}% year-over-year according to new data.",
            ]
            return rng.choice(snippets)
        if name == "kb_search":
            q = args.get("query", "").lower()
            for k, v in cls._kb_topics.items():
                if k in q:
                    return v
            return "No matching article found."
        if name == "fetch_url":
            words = rng.randint(200, 800)
            return f"[page content from {args.get('url', '?')}]: retrieved {words} words"
        return f"[mcp:{name}] ok"

    @classmethod
    def subagent(cls, name: str, args: dict, context: str, rng: random.Random) -> str:
        """Run a simulated sub-agent over ``context``."""
        if name == "summarise":
            words = rng.randint(40, 120)
            pts = rng.randint(2, 5)
            return f"Summary ({words} words): {context[:80]}… Key points: {pts} identified."
        if name == "draft_email":
            tone = rng.choice(cls._email_tones)
            return f"[{tone} email draft] Dear customer, regarding your request: {context[:60]}…"
        if name == "analyse":
            n = rng.randint(2, 6)
            return f"Analysis complete. {n} factors identified from: {context[:60]}…"
        return f"[subagent:{name}] processed: {context[:50]}"
