"""``BaseLLMProvider`` — shared base for HTTP LLM provider connectors.

Concrete providers (an OpenAI-compatible adapter, a Messages-API adapter, …)
are thin subclasses that supply only *request-shaping* and *response-parsing*;
everything cross-cutting lives here:

* **Retries** — jittered exponential backoff via
  :class:`pirn_agents.llm.retry_policy.RetryPolicy`, with HTTP 429 handled
  distinctly (honouring a server ``Retry-After``) from transient 5xx/network
  errors, and non-retryable 4xx propagated immediately.
* **Lifecycle** — a pooled async HTTP client vended once by
  :class:`pirn_agents.connector_base.ConnectorBase` and imported lazily via
  :func:`pirn_agents._require._require` so ``import pirn_agents`` stays
  backend-free.
* **Response mapping** — raw provider JSON is mapped to
  :class:`pirn_agents.types.agent_response.AgentResponse` (content, tool calls,
  finish reason, usage) with native tool calls decoded through F1's
  :class:`pirn_agents.tool_call_codec.ToolCallCodec`.
* **Streaming** — :meth:`stream_chat` yields a unified
  :class:`pirn_agents.llm.stream_delta.StreamDelta` (token + incremental
  tool-call fragments) and always closes the underlying stream, even on
  cancellation.
* **Caching + cost** — an opt-in prompt/context-caching hook
  (:meth:`_apply_prompt_cache`, a no-op unless a subclass overrides it) plus
  usage/cost accounting from a :class:`pirn_agents.llm.model_pricing.ModelPricing`.

The base is provider-neutral: it never names a vendor and imports nothing
provider-specific. Subclasses override the ``_``-prefixed shaping/parsing
hooks below.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Mapping, Sequence
from typing import Any

from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.connector_base import ConnectorBase
from pirn_agents.credential_ref import CredentialRef
from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.rate_limit_error import RateLimitError
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.llm.transient_llm_error import TransientLLMError
from pirn_agents.provider_adapter import ProviderAdapter
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from pirn_agents.streaming_tool_call_parser import StreamingToolCallParser
from pirn_agents.tool_call_codec import ToolCallCodec
from pirn_agents.toolset import Toolset
from pirn_agents.types.agent_response import AgentResponse


class BaseLLMProvider(ConnectorBase, LLMProvider):
    """Base HTTP LLM provider: retries, mapping, streaming, cost accounting."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        credential: CredentialRef | None = None,
        retry_policy: RetryPolicy | None = None,
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
            retry_policy: Retry/backoff policy; a default is used when ``None``.
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
        if retry_policy is not None and not isinstance(retry_policy, RetryPolicy):
            raise TypeError(
                f"retry_policy must be a RetryPolicy or None, got {type(retry_policy).__name__}"
            )
        if pricing is not None and not isinstance(pricing, ModelPricing):
            raise TypeError(f"pricing must be a ModelPricing or None, got {type(pricing).__name__}")
        self._model: str = model
        self._base_url: str = base_url
        self._retry_policy: RetryPolicy = (
            retry_policy if retry_policy is not None else RetryPolicy()
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

    # -- pooled-client construction -------------------------------------

    async def _create_client(self) -> Any:
        """Return the injected client, or lazily build a pooled ``httpx`` one.

        The real client is imported through :func:`_require` so ``httpx`` is
        never imported at package-import time; tests inject a fake client and
        never reach the import.
        """
        if self._injected_client is not None:
            return self._injected_client
        httpx = self._require("web", "httpx")
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
        return self._response_to_mapping(response)

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
        data = await self._request_with_retries(payload)
        return self._parse_completion(data)

    # -- structured output (F20) capability surface ---------------------

    def structured_output_capability(self) -> StructuredOutputCapability:
        """Return this provider's native structured-output capability flags.

        The base advertises no native support, so a bare provider routes the
        unified structured decoder straight to the extract-validate-retry
        fallback. Providers whose wire format supports native schema decoding,
        forced tool-choice, or constrained decoding override this to opt in.
        """
        return StructuredOutputCapability()

    async def structured_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: Toolset | None = None,
        request_options: Mapping[str, Any] | None = None,
    ) -> AgentResponse:
        """Send a chat completion merging ``request_options`` into the request.

        Identical to :meth:`chat_response` but for the extra ``request_options``
        (a native ``response_format`` / ``tool_choice`` / constrained-decoding
        fragment produced by an F20 strategy), which are merged into the shaped
        request body. When ``request_options`` is empty the request is byte-for-
        byte the same as :meth:`chat_response`, so existing behavior is
        unchanged.
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
        if request_options:
            payload = self._merge_request_options(payload, request_options)
        data = await self._request_with_retries(payload)
        return self._parse_completion(data)

    @staticmethod
    def _merge_request_options(
        payload: dict[str, Any], request_options: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Merge ``request_options`` into ``payload``, deep-merging ``extra_body``.

        Top-level keys are overlaid onto the payload; ``extra_body`` (used by
        local engines for guided-decoding fields) is merged one level deep so a
        strategy's constraint keys join, rather than clobber, any existing ones.
        """
        merged = dict(payload)
        for key, value in request_options.items():
            if key == "extra_body" and isinstance(value, Mapping):
                existing = merged.get("extra_body")
                base = dict(existing) if isinstance(existing, Mapping) else {}
                merged["extra_body"] = {**base, **dict(value)}
            else:
                merged[key] = value
        return merged

    def native_schema_option(self, schema: Mapping[str, Any], *, name: str) -> Mapping[str, Any]:
        """Return native request options carrying ``schema`` (provider-specific).

        Only invoked when :meth:`structured_output_capability` advertises
        ``native_schema``; the base raises so a misconfigured provider fails
        loudly rather than silently.
        """
        raise NotImplementedError(
            f"{type(self).__name__} advertises native_schema but does not "
            "implement native_schema_option()"
        )

    def forced_tool_choice_option(self, tool_name: str) -> Mapping[str, Any]:
        """Return request options forcing tool-choice to ``tool_name``.

        Only invoked when :meth:`structured_output_capability` advertises
        ``forced_tool_choice``; the base raises otherwise.
        """
        raise NotImplementedError(
            f"{type(self).__name__} advertises forced_tool_choice but does not "
            "implement forced_tool_choice_option()"
        )

    def constrained_decoding_option(self, constraint: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return request options passing a grammar/regex decoding ``constraint``.

        Only invoked when :meth:`structured_output_capability` advertises
        ``constrained_decoding``; the base raises otherwise.
        """
        raise NotImplementedError(
            f"{type(self).__name__} advertises constrained_decoding but does not "
            "implement constrained_decoding_option()"
        )

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: Toolset | None = None,
    ) -> AsyncIterator[StreamDelta]:
        """Yield unified :class:`StreamDelta` fragments for ``messages``.

        Tokens are yielded as they arrive (before completion); tool calls
        arrive as incremental fragments. The underlying HTTP stream is always
        closed on exit — including consumer cancellation or a mid-stream
        error — via ``async with``, so no connection leaks.
        """
        payload = self._build_request(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            tools=tools,
        )
        self._apply_prompt_cache(payload)
        client = await self._get_client()
        url = self._url(self._completions_path())
        headers = self._request_headers()
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            status = int(response.status_code)
            if not 200 <= status < 300:
                raise LLMHTTPStatusError(f"stream failed with http {status}", status_code=status)
            async for delta in self._iter_stream(response):
                yield delta

    async def stream_response(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: Toolset | None = None,
    ) -> AgentResponse:
        """Drain :meth:`stream_chat` into a complete :class:`AgentResponse`."""
        return await self.collect_stream(
            self.stream_chat(
                messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
            )
        )

    async def collect_stream(self, deltas: AsyncIterable[StreamDelta]) -> AgentResponse:
        """Fold a stream of :class:`StreamDelta` into one :class:`AgentResponse`.

        Content fragments are concatenated; tool-call fragments are assembled
        into decodable :class:`~pirn_agents.types.tool_call.ToolCall`s via
        :class:`StreamingToolCallParser`; the last non-``None`` finish reason
        and usage win; cost is estimated when pricing is configured.
        """
        content_parts: list[str] = []
        finish_reason = "stop"
        usage: dict[str, int] = {}
        tool_deltas: list[Mapping[str, Any]] = []
        async for delta in deltas:
            if delta.content:
                content_parts.append(delta.content)
            if delta.finish_reason is not None:
                finish_reason = delta.finish_reason
            if delta.usage is not None:
                usage = {**usage, **dict(delta.usage)}
            if delta.tool_call is not None:
                tool_deltas.append(delta.tool_call)

        async def _emit() -> AsyncIterator[Mapping[str, Any]]:
            for fragment in tool_deltas:
                yield fragment

        calls = tuple(await StreamingToolCallParser().parse_to_list(_emit()))
        cost = self._pricing.estimate_cost(usage) if self._pricing is not None else None
        return AgentResponse(
            content="".join(content_parts),
            tool_calls=calls,
            finish_reason=finish_reason,
            usage=usage,
            cost=cost,
        )

    # -- retry / transport ----------------------------------------------

    async def _request_with_retries(self, payload: Mapping[str, Any]) -> Any:
        """POST ``payload`` with jittered-backoff retries and 429 handling.

        Retries HTTP 429 (honouring ``Retry-After`` when present) and transient
        5xx/network errors up to the policy's ``max_retries``; propagates
        non-retryable errors immediately.
        """
        attempt = 0
        while True:
            try:
                return await self._post_json(payload)
            except RateLimitError as exc:
                if attempt >= self._retry_policy.max_retries:
                    raise
                delay = (
                    exc.retry_after
                    if exc.retry_after is not None
                    else self._retry_policy.backoff_delay(attempt, rng=self._rng)
                )
                await self._sleep(delay)
            except TransientLLMError:
                if attempt >= self._retry_policy.max_retries:
                    raise
                await self._sleep(self._retry_policy.backoff_delay(attempt, rng=self._rng))
            attempt += 1

    async def _post_json(self, payload: Mapping[str, Any]) -> Any:
        """Perform one POST and return parsed JSON, mapping errors to types.

        Maps status codes to typed errors: ``429`` → ``RateLimitError``;
        ``5xx`` → ``TransientLLMError``; other non-2xx → ``LLMHTTPStatusError``.
        Transport-level exceptions (timeouts, resets) become
        ``TransientLLMError`` so they retry.
        """
        client = await self._get_client()
        url = self._url(self._completions_path())
        headers = self._request_headers()
        try:
            response = await client.post(url, json=dict(payload), headers=headers)
        except Exception as exc:
            if isinstance(exc, (RateLimitError, TransientLLMError, LLMHTTPStatusError)):
                raise
            if self._is_transient_transport_error(exc):
                raise TransientLLMError(str(exc)) from exc
            raise
        status = int(response.status_code)
        if status == 429:
            raise RateLimitError("provider returned 429", retry_after=self._retry_after(response))
        if 500 <= status < 600:
            raise TransientLLMError(f"provider server error {status}", status_code=status)
        if not 200 <= status < 300:
            raise LLMHTTPStatusError(f"provider returned http {status}", status_code=status)
        return response.json()

    def _request_headers(self) -> dict[str, str]:
        """Return the merged base + provider-specific auth headers."""
        headers = {"content-type": "application/json"}
        headers.update(self._auth_headers())
        return headers

    def _url(self, path: str) -> str:
        """Join the configured base URL with ``path``."""
        return f"{self._base_url.rstrip('/')}{path}"

    @staticmethod
    def _retry_after(response: Any) -> float | None:
        """Parse a ``Retry-After`` header (seconds) from ``response``, if any."""
        headers = getattr(response, "headers", None) or {}
        raw = headers.get("retry-after") if hasattr(headers, "get") else None
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_transient_transport_error(exc: BaseException) -> bool:
        """Return whether ``exc`` is a retryable ``httpx`` transport error.

        Detection is by module + class name so this module never imports
        ``httpx`` (keeping ``import pirn_agents`` backend-free).
        """
        module = (type(exc).__module__ or "").split(".", 1)[0]
        if module != "httpx":
            return False
        transient_names = {
            "TimeoutException",
            "ConnectTimeout",
            "ReadTimeout",
            "WriteTimeout",
            "PoolTimeout",
            "ConnectError",
            "ReadError",
            "WriteError",
            "NetworkError",
            "TransportError",
            "RemoteProtocolError",
        }
        return type(exc).__name__ in transient_names

    # -- response mapping -----------------------------------------------

    def _parse_completion(self, data: Mapping[str, Any]) -> AgentResponse:
        """Map raw provider JSON ``data`` to an :class:`AgentResponse`."""
        usage = self._usage_tokens(data)
        cost = self._pricing.estimate_cost(usage) if self._pricing is not None else None
        return AgentResponse(
            content=self._content_text(data),
            tool_calls=tuple(self._codec.decode_calls(self._tool_message(data))),
            finish_reason=self._finish_reason(data),
            usage=usage,
            cost=cost,
        )

    def _response_to_mapping(self, response: AgentResponse) -> dict[str, Any]:
        """Render an :class:`AgentResponse` as a plain mapping."""
        return {
            "content": response.content,
            "tool_calls": [dict(call.arguments) for call in response.tool_calls],
            "finish_reason": response.finish_reason,
            "usage": dict(response.usage),
            "cost": response.cost,
        }

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
        """Extract the neutral finish reason from a raw response."""
        raise NotImplementedError(f"{type(self).__name__} must implement _finish_reason()")

    def _usage_tokens(self, data: Mapping[str, Any]) -> dict[str, int]:
        """Extract a neutral token-usage mapping from a raw response."""
        raise NotImplementedError(f"{type(self).__name__} must implement _usage_tokens()")

    def _iter_stream(self, response: Any) -> AsyncIterator[StreamDelta]:
        """Parse a streaming HTTP response into neutral :class:`StreamDelta`s."""
        raise NotImplementedError(f"{type(self).__name__} must implement _iter_stream()")
