# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``BaseLLMProvider`` — thin orchestrator for HTTP LLM provider connectors.

Concrete providers (an OpenAI-compatible adapter, a Messages-API adapter, …)
are thin subclasses that supply only *request-shaping* and *response-parsing*;
the cross-cutting work is delegated to injected collaborators so this base stays
a lean orchestrator (DIP):

* **Retries / transport** — a :class:`pirn_agents.llm.http_transport.HttpTransport`
  owns the POST + jittered exponential backoff, with HTTP 429 handled distinctly
  (honouring a server ``Retry-After``) from transient 5xx/network errors and
  non-retryable 4xx propagated immediately.
* **Response mapping** — a :class:`pirn_agents.llm.response_mapper.ResponseMapper`
  folds the primitives this base pulls from the raw provider JSON (content, tool
  message, finish reason, usage) into a
  :class:`pirn_agents.types.messaging.agent_response.AgentResponse`, decoding native tool
  calls through F1's :class:`pirn_agents.tools.tool_call_codec.ToolCallCodec` and
  estimating cost from a :class:`pirn_agents.llm.model_pricing.ModelPricing`.
* **Lifecycle** — a pooled async HTTP client vended once by
  :class:`pirn.connectors.connector_base.ConnectorBase` and imported lazily via
  :meth:`~pirn.core.optional_dependency.OptionalDependency.require` so ``import pirn_agents`` stays
  backend-free.
* **Streaming** — :meth:`stream_chat` yields a unified
  :class:`pirn_agents.llm.stream_delta.StreamDelta` (token + incremental
  tool-call fragments) and always closes the underlying stream, even on
  cancellation.
* **Caching** — an opt-in prompt/context-caching hook (:meth:`_apply_prompt_cache`,
  a no-op unless a subclass overrides it).

This base is a plain :class:`pirn_agents.llm.llm_provider.LLMProvider`: it carries no
structured-output surface, so plain-chat clients never depend on the F20 seam
(ISP). HTTP providers that support native structured output subclass
:class:`pirn_agents.llm.http_structured_output_provider.HttpStructuredOutputProvider`
instead. The base is provider-neutral: it never names a vendor and imports
nothing provider-specific. Subclasses override the ``_``-prefixed shaping/parsing
hooks below.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from typing import Any

from pirn.connectors.connector_base import ConnectorBase
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.optional_dependency import OptionalDependency
from pirn.security.credential_ref import CredentialRef

from pirn_agents.llm.http_transport import HttpTransport
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.llm_provider_identity_mixin import LLMProviderIdentityMixin
from pirn_agents.llm.llm_provider_multimodal_mixin import LLMProviderMultimodalMixin
from pirn_agents.llm.llm_provider_streaming_mixin import LLMProviderStreamingMixin
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.provider_adapter import ProviderAdapter
from pirn_agents.llm.response_mapper import ResponseMapper
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.tools.tool_call_codec import ToolCallCodec
from pirn_agents.tools.toolset import Toolset
from pirn_agents.types.messaging.agent_response import AgentResponse


class BaseLLMProvider(
    LLMProviderIdentityMixin,
    LLMProviderMultimodalMixin,
    LLMProviderStreamingMixin,
    ConnectorBase,
    LLMProvider,
):
    """Thin HTTP LLM provider orchestrator: retries, mapping, streaming, cost.

    Mixin order is load-bearing, not stylistic: :class:`LLMProviderIdentityMixin`
    overrides :meth:`~pirn.connectors.connector_base.ConnectorBase.__pirn_canonical__`
    and calls ``super().__pirn_canonical__()`` to fall back to the identity-keyed
    base implementation, so the mixins must precede
    :class:`~pirn.connectors.connector_base.ConnectorBase` in the MRO — placing
    ``ConnectorBase`` first would let its ``__pirn_canonical__`` shadow the
    mixin's override instead of being ``super()``'s target.
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        credential: CredentialRef | None = None,
        retry_policy: KnotRetryPolicy | None = None,
        pricing: ModelPricing | None = None,
        timeout: float = 30.0,
        default_max_tokens: int | None = None,
        enable_prompt_cache: bool = False,
        client: Any | None = None,
        sleeper: Callable[[float], Awaitable[None]] | None = None,
        rng: Callable[[], float] | None = None,
    ) -> None:
        """Initialise shared provider state and validate configuration.

        Args:
            model: Default model identifier used when a call omits ``model``.
            base_url: Base endpoint URL (e.g. ``https://host/v1``); the
                provider's completions path is appended to it.
            credential: Optional API-key :class:`CredentialRef`.
            retry_policy: Retry/backoff policy for each request; ``None`` uses
                ``KnotRetryPolicy(max_attempts=3)`` (the first attempt plus two
                retries).
            pricing: Optional per-model price sheet enabling cost estimation.
            timeout: Per-request timeout, in seconds, for the real HTTP client.
            default_max_tokens: Default output-token cap applied when a call
                omits ``max_tokens``.
            enable_prompt_cache: Opt-in flag for the prompt/context caching
                hook; a no-op for providers without native support.
            client: Optional pre-built async HTTP client (injected in tests to
                avoid any real network / backend import).
            sleeper: Optional async sleep function (injected in tests);
                defaults to :func:`asyncio.sleep`.
            rng: Optional jitter source returning a float in ``[0, 1)``;
                defaults to the policy's own :func:`random.random`.

        Raises:
            TypeError: If ``model``/``base_url`` are not strings, or
                ``retry_policy``/``pricing`` are of the wrong type.
        """
        super().__init__(credential=credential)
        if not isinstance(model, str):
            raise TypeError(f"model must be a str, got {type(model).__name__}")
        if not isinstance(base_url, str):
            raise TypeError(f"base_url must be a str, got {type(base_url).__name__}")
        if retry_policy is not None and not isinstance(retry_policy, KnotRetryPolicy):
            raise TypeError(
                f"retry_policy must be a KnotRetryPolicy or None, got {type(retry_policy).__name__}"
            )
        if pricing is not None and not isinstance(pricing, ModelPricing):
            raise TypeError(f"pricing must be a ModelPricing or None, got {type(pricing).__name__}")
        self._model: str = model
        self._base_url: str = base_url
        self._retry_policy: KnotRetryPolicy = (
            retry_policy if retry_policy is not None else KnotRetryPolicy(max_attempts=3)
        )
        self._pricing: ModelPricing | None = pricing
        self._timeout: float = float(timeout)
        self._default_max_tokens: int | None = default_max_tokens
        self._enable_prompt_cache: bool = bool(enable_prompt_cache)
        self._injected_client: Any | None = client
        self._sleep: Callable[[float], Awaitable[None]] = (
            sleeper if sleeper is not None else asyncio.sleep
        )
        self._rng: Callable[[], float] | None = rng
        self._codec: ToolCallCodec = ToolCallCodec(self._tool_adapter())
        self._mapper: ResponseMapper = ResponseMapper(codec=self._codec, pricing=self._pricing)
        self._transport: HttpTransport = HttpTransport(
            retry_policy=self._retry_policy, sleeper=self._sleep, rng=self._rng
        )

    # -- pooled-client construction -------------------------------------

    async def _create_client(self) -> Any:
        """Return the injected client, or lazily build a pooled ``httpx`` one.

        The real client is imported through :meth:`~pirn.core.optional_dependency.OptionalDependency.require` so ``httpx`` is
        never imported at package-import time; tests inject a fake client and
        never reach the import.
        """
        if self._injected_client is not None:
            return self._injected_client
        httpx = OptionalDependency.require("httpx", extra="web", package="pirn-agents")
        return httpx.AsyncClient(timeout=self._timeout)

    # -- public API (LLMProvider) ---------------------------------------

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        """Send a chat completion and return the normalised response mapping.

        The mapping exposes ``content``/``tool_calls``/``finish_reason``/
        ``usage``/``cost`` so plain consumers (and ReAct-style loops that read
        ``content``) work without importing pirn types.
        """
        response = await self.chat_response(
            messages, model=model, max_tokens=max_tokens, temperature=temperature
        )
        return ResponseMapper.to_mapping(response)

    async def chat_response(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: Toolset | None = None,
    ) -> AgentResponse:
        """Send a chat completion and return a typed :class:`AgentResponse`.

        Applies retries/backoff and maps the raw provider JSON to an
        :class:`AgentResponse`, decoding native tool calls via the codec and
        populating usage + estimated cost.
        """
        payload = self._build_request(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
            tools=tools,
        )
        self._apply_prompt_cache(payload)
        return await self._complete(payload)

    # -- transport orchestration ----------------------------------------

    async def _complete(self, payload: dict[str, Any]) -> AgentResponse:
        """Send ``payload`` via the transport and map the reply to a response.

        Resolves the pooled client, endpoint URL, and auth headers, delegates
        the retried POST to :class:`HttpTransport`, and folds the raw JSON into
        an :class:`AgentResponse` via :class:`ResponseMapper`.
        """
        client = await self._get_client()
        url = self._url(self._completions_path())
        headers = self._request_headers()
        data = await self._transport.request_with_retries(
            client=client, url=url, headers=headers, payload=payload
        )
        return self._parse_completion(data)

    def _request_headers(self) -> dict[str, str]:
        """Return the merged base + provider-specific auth headers."""
        headers = {"content-type": "application/json"}
        headers.update(self._auth_headers())
        return headers

    def _url(self, path: str) -> str:
        """Join the configured base URL with ``path``."""
        return f"{self._base_url.rstrip('/')}{path}"

    # -- response mapping -----------------------------------------------

    def _parse_completion(self, data: Mapping[str, Any]) -> AgentResponse:
        """Map raw provider JSON ``data`` to an :class:`AgentResponse`."""
        return self._mapper.to_agent_response(
            content=self._content_text(data),
            tool_message=self._tool_message(data),
            finish_reason=self._finish_reason(data),
            usage=self._usage_tokens(data),
        )

    # -- caching hook (opt-in; no-op by default) ------------------------

    def _apply_prompt_cache(self, payload: dict[str, Any]) -> None:
        """Mutate ``payload`` to enable prompt/context caching, if supported.

        The base implementation is a no-op: providers without native caching
        leave the request shape unchanged even when ``enable_prompt_cache`` is
        set. Providers with native support override this.
        """
        return None

    # -- provider-specific hooks (overridden by adapters) ---------------

    def _tool_adapter(self) -> ProviderAdapter:
        """Return the :class:`ProviderAdapter` for native tool-call mapping."""
        raise NotImplementedError(f"{type(self).__name__} must implement _tool_adapter()")

    def _completions_path(self) -> str:
        """Return the path (appended to ``base_url``) for chat completions."""
        raise NotImplementedError(f"{type(self).__name__} must implement _completions_path()")

    def _auth_headers(self) -> dict[str, str]:
        """Return provider-specific authentication headers."""
        raise NotImplementedError(f"{type(self).__name__} must implement _auth_headers()")

    def _build_request(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None,
        max_tokens: int | None,
        temperature: float | None,
        stream: bool,
        tools: Toolset | None,
    ) -> dict[str, Any]:
        """Shape a request body for this provider's wire format."""
        raise NotImplementedError(f"{type(self).__name__} must implement _build_request()")

    def _content_text(self, data: Mapping[str, Any]) -> str:
        """Extract the assistant text content from a raw response."""
        raise NotImplementedError(f"{type(self).__name__} must implement _content_text()")

    def _tool_message(self, data: Mapping[str, Any]) -> Any:
        """Return the object the codec decodes native tool calls from."""
        raise NotImplementedError(f"{type(self).__name__} must implement _tool_message()")

    def _finish_reason(self, data: Mapping[str, Any]) -> str:
        """Extract the finish reason from a raw response.

        Implementations map their own wire values onto the neutral
        :class:`~pirn_agents.types.messaging.finish_reason.FinishReason`
        vocabulary, surfacing unrecognised values verbatim.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement _finish_reason()")

    def _usage_tokens(self, data: Mapping[str, Any]) -> dict[str, int]:
        """Extract a neutral token-usage mapping from a raw response."""
        raise NotImplementedError(f"{type(self).__name__} must implement _usage_tokens()")

    def _iter_stream(self, response: Any) -> AsyncIterator[StreamDelta]:
        """Parse a streaming HTTP response into neutral :class:`StreamDelta`s."""
        raise NotImplementedError(f"{type(self).__name__} must implement _iter_stream()")
