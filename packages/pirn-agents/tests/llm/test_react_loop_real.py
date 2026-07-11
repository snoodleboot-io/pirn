"""Opt-in local/self-hosted validation (PAE-F3-S7 / PIR-73, PIR-130).

Runs :class:`ReActLoop` end-to-end through the OpenAI-compatible adapter
against a *real* locally-running, self-hosted backend (vLLM or Ollama, both of
which expose the ``/v1/chat/completions`` wire format). It is opt-in and
excluded from default CI: it only runs when ``--real`` is passed AND
``PIRN_REAL_LLM_BASE_URL`` names a reachable endpoint. This keeps CI stub-only
and hermetic while giving a one-command path to validate a live engine.

Run it with, e.g. (Ollama)::

    PIRN_REAL_LLM_BASE_URL=http://localhost:11434/v1 \
    PIRN_REAL_LLM_MODEL=llama3.1 \
    .venv/bin/python -m pytest tests/llm/test_react_loop_real.py --real -q -s

or (vLLM)::

    PIRN_REAL_LLM_BASE_URL=http://localhost:8000/v1 \
    PIRN_REAL_LLM_MODEL=$MODEL \
    .venv/bin/python -m pytest tests/llm/test_react_loop_real.py --real -q -s

See ``pirn_agents/llm/LLM_PROVIDERS.md`` for setup and known behavioural gaps.
"""

from __future__ import annotations

import os

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.credential_ref import CredentialRef
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse
from tests.specializations.conftest import StubTool


async def test_react_loop_against_real_local_backend(request: pytest.FixtureRequest) -> None:
    if not request.config.getoption("--real"):
        pytest.skip("real-backend run is opt-in; pass --real with PIRN_REAL_LLM_BASE_URL set")
    base_url = os.environ.get("PIRN_REAL_LLM_BASE_URL")
    if not base_url:
        pytest.skip("set PIRN_REAL_LLM_BASE_URL to a running vLLM/Ollama /v1 endpoint")

    model = os.environ.get("PIRN_REAL_LLM_MODEL", "llama3.1")
    api_key = os.environ.get("PIRN_REAL_LLM_API_KEY")
    credential = CredentialRef(api_key) if api_key else None

    provider = OpenAICompatibleProvider(
        model=model,
        base_url=base_url,
        credential=credential,
        default_max_tokens=256,
    )
    try:
        tool = StubTool(name="search", handler="found foo")
        with Tapestry() as tapestry:
            ReActLoop(
                messages=(AgentMessage(role="user", content="Say 'Final Answer: done'."),),
                llm=provider,
                tools=(tool,),
                max_iterations=3,
                _config=KnotConfig(id="loop"),
            )
        run = await tapestry.run(RunRequest())
        assert run.succeeded
        response = run.outputs["loop"]
        assert isinstance(response, AgentResponse)
        assert isinstance(response.content, str)
    finally:
        await provider.close()
