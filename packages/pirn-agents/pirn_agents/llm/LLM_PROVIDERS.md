# LLM Provider Connectors (PAE-F3 / PIR-16)

Concrete `LLMProvider` implementations behind the `pirn-core` interface. Every
provider is a **peer plugin** — treated identically, provider-neutral, and kept
out of the base install. Importing `pirn_agents` (or any of its submodules)
pulls in **no** HTTP client or vendor SDK; the transport is imported lazily at
first use.

## Adapters

| Class | Wire format | Serves |
|-------|-------------|--------|
| `OpenAICompatibleProvider` | `POST {base_url}/chat/completions` | any server speaking the chat-completions protocol — self-hosted vLLM/Ollama, gateways, hosted endpoints |
| `AnthropicMessagesProvider` | `POST {base_url}/messages` | a distinct request/response shape (content blocks, `tool_use`/`tool_result`, typed SSE), added as an equal peer for balance |

Both are thin `BaseLLMProvider` subclasses supplying only request-shaping and
response-parsing. Shared behaviour (retries + jittered backoff, distinct HTTP
429 handling, transient/transport retries, response → `AgentResponse` mapping,
native tool-calling via F1's `ToolCallCodec`, unified streaming deltas,
prompt-cache hook, usage/cost accounting) lives in `BaseLLMProvider`.

## Install (extras)

The HTTP transport (`httpx`) is the only backend either adapter needs, so both
live behind the existing **`web`** extra. The base package never imports it.

```bash
pip install "pirn-agents[web]"     # enables the HTTP LLM adapters
```

Until the extra is installed, the adapters import fine but the first network
call raises an actionable error:

```
ImportError: 'httpx' is required for this feature; install it with:
pip install "pirn-agents[web]"
```

Discover availability at runtime without importing the backend:

```python
from pirn_agents import available_extras
available_extras()["web"]   # True once httpx is installed
```

## Minimal usage

```python
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.llm.openai_compatible_provider import OpenAICompatibleProvider
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.retry_policy import RetryPolicy

provider = OpenAICompatibleProvider(
    model="my-model",
    base_url="https://host/v1",                 # e.g. http://localhost:11434/v1 (Ollama)
    credential=CredentialRef("sk-..."),          # optional; omitted for keyless local servers
    retry_policy=RetryPolicy(max_retries=3),
    pricing=ModelPricing(input_per_million=0.5, output_per_million=1.5),
)

# Typed response (content, tool_calls, finish_reason, usage, cost):
response = await provider.chat_response([{"role": "user", "content": "hello"}])

# Streaming: tokens (and incremental tool-call fragments) arrive before completion:
async for delta in provider.stream_chat([{"role": "user", "content": "hello"}]):
    print(delta.content, end="")

await provider.close()   # releases the pooled client and scrubs the credential
```

Native tool-calling: pass a `Toolset` to `chat_response`/`stream_chat`; tools are
encoded to the provider's native shape and returned tool calls (single **or**
parallel) are decoded to `ToolCall`s with their call IDs preserved.

Prompt/context caching is opt-in via `enable_prompt_cache=True`. It is a **no-op**
for adapters without native support (e.g. the OpenAI-compatible one, where the
request shape is unchanged) and active where supported (`AnthropicMessagesProvider`
marks the system prompt with `cache_control`).

## Local / self-hosted validation (`--real`)

CI is **stub-only**: every test injects a fake async transport, so no network
calls or real keys are used. To validate against a real, locally-running,
self-hosted backend, use the opt-in `--real` path:

```bash
# Ollama
PIRN_REAL_LLM_BASE_URL=http://localhost:11434/v1 \
PIRN_REAL_LLM_MODEL=llama3.1 \
.venv/bin/python -m pytest tests/llm/test_react_loop_real.py --real -q -s

# vLLM (OpenAI-compatible server)
PIRN_REAL_LLM_BASE_URL=http://localhost:8000/v1 \
PIRN_REAL_LLM_MODEL=<served-model-id> \
PIRN_REAL_LLM_API_KEY=<token-if-required> \
.venv/bin/python -m pytest tests/llm/test_react_loop_real.py --real -q -s
```

The test runs `ReActLoop` end-to-end through `OpenAICompatibleProvider`. Without
`--real` (or without `PIRN_REAL_LLM_BASE_URL`) it skips, so it never gates CI.

### Known gaps vs. hosted OpenAI-compatible endpoints

Self-hosted servers implement the chat-completions protocol with varying
completeness. Observed differences to expect:

- **Usage in streaming.** Some vLLM/Ollama versions omit the final `usage`
  chunk (no `stream_options.include_usage` support). Streamed `usage`/`cost`
  may then be empty even though non-streaming responses report it.
- **Tool calling.** Native `tools`/`tool_calls` support is model- and
  version-dependent; older Ollama builds ignore `tools` and return plain text.
  The ReAct text protocol still works without native tool calling.
- **`finish_reason`.** Some servers always return `"stop"` and never emit
  `"tool_calls"`/`"length"`.
- **Prompt caching.** Not exposed by the chat-completions protocol; the caching
  hook is a no-op for this adapter regardless of the `enable_prompt_cache` flag.
- **Auth.** Local servers are frequently keyless; omit `credential` (no
  `Authorization` header is sent).
