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
  :func:`pirn_agents._internal._require._require` so ``import pirn_agents`` stays
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
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Mapping, Sequence
from typing import Any

from pirn.connectors.connector_base import ConnectorBase
from pirn.security.credential_ref import CredentialRef

from pirn_agents.exceptions.unsupported_modality_error import UnsupportedModalityError
from pirn_agents.llm.endpoint_identity import EndpointIdentity
from pirn_agents.llm.http_transport import HttpTransport
from pirn_agents.llm.llm_http_status_error import LLMHTTPStatusError
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.modality_capability import ModalityCapability
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.multimodal_adapter import MultimodalAdapter
from pirn_agents.llm.provider_adapter import ProviderAdapter
from pirn_agents.llm.response_mapper import ResponseMapper
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.tools.definition_reference import DefinitionReference
from pirn_agents.tools.streaming_tool_call_parser import StreamingToolCallParser
from pirn_agents.tools.tool_call_codec import ToolCallCodec
from pirn_agents.tools.toolset import Toolset
from pirn_agents.types.content.content_block import ContentBlock
from pirn_agents.types.messaging.agent_response import AgentResponse


class BaseLLMProvider(ConnectorBase, LLMProvider):
    """Thin HTTP LLM provider orchestrator: retries, mapping, streaming, cost."""

    # The httpx backend ships with pirn-agents, so the missing-dependency install
    # hint must name this distribution, not core's.
    _install_dist = "pirn-agents"

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
        self._mapper: ResponseMapper = ResponseMapper(codec=self._codec, pricing=self._pricing)
        self._transport: HttpTransport = HttpTransport(
            retry_policy=self._retry_policy, sleeper=self._sleep, rng=self._rng
        )

    # -- content identity (PIR-840) --------------------------------------

    def content_identity(self) -> Mapping[str, Any] | None:
        """Return the secret-free config that determines this provider's responses, or ``None``.

        The returned mapping holds every constructor input that can change what a
        call returns: the model, the endpoint (scheme, host, port and path only; see
        :class:`~pirn_agents.llm.endpoint_identity.EndpointIdentity`), the default
        output-token cap, the prompt-cache flag, the pricing sheet (it sets the
        response's ``cost``), the request timeout and the retry policy (both decide
        whether a slow or flaky call returns a response or an error).

        The credential is deliberately **not** part of it. Two providers that differ
        only in API key replay each other's recordings; a secret is never identity
        and never reaches lineage.

        ``None`` (stay identity-keyed) is returned whenever the provider's behaviour
        depends on something this mapping cannot capture safely:

        * the base URL has userinfo, a query string or a fragment, or is otherwise
          not reducible to the allowlisted components;
        * an HTTP ``client``, ``sleeper`` or ``rng`` was injected, or the transport
          was replaced (a test double or custom client can return anything);
        * the pricing or retry policy is a subclass of its value type, or a numeric
          setting is not a plain number.

        Pricing, retry policy, sleeper and jitter source are read from the
        collaborators the constructor built (the response mapper and the transport),
        not from the provider's own attributes, so the hash describes what actually
        runs. Mutating any private attribute after construction (``_pricing``,
        ``_mapper``, ``_transport``, …) or monkeypatching a method is unsupported:
        the hash is only guaranteed to match behaviour for a provider configured
        through its constructor.

        The opt-in is **not inherited**, following the rule tools use: only a class
        that defines ``content_identity`` itself is content-identified. A concrete
        provider re-declares it (usually as ``return super().content_identity()``)
        to assert that these fields are its whole behaviour-relevant config; a
        subclass that adds constructor arguments, headers or request fields must
        re-declare it with those included, or it stays identity-keyed.

        Accepted limitation: ``httpx`` reads proxy and TLS trust settings
        (``HTTP(S)_PROXY``, ``SSL_CERT_FILE``, …) from the environment. They are not
        hashed, because they are process-wide and proxy URLs often carry credentials.
        """
        if self._injected_client is not None:
            return None
        transport = self._transport
        mapper = self._mapper
        if type(transport) is not HttpTransport or type(mapper) is not ResponseMapper:
            return None
        if transport.sleeper is not asyncio.sleep or transport.rng is not None:
            return None
        endpoint = EndpointIdentity.of(self._base_url)
        if endpoint is None:
            return None
        running_pricing = mapper.pricing
        pricing = None if running_pricing is None else self._pricing_identity(running_pricing)
        if running_pricing is not None and pricing is None:
            return None
        retry_policy = self._retry_policy_identity(transport.retry_policy)
        if retry_policy is None:
            return None
        max_tokens = self._default_max_tokens
        if max_tokens is not None and not self._is_plain_int(max_tokens):
            return None
        if not self._is_plain_number(self._timeout):
            return None
        return {
            "model": self._model,
            "endpoint": endpoint,
            "default_max_tokens": max_tokens,
            "enable_prompt_cache": self._enable_prompt_cache,
            "pricing": pricing,
            "timeout": self._timeout,
            "retry_policy": retry_policy,
        }

    def __pirn_canonical__(self) -> Any:
        """Return the form :func:`pirn.core.hashing.content_hash` hashes.

        The provider is content-identified only when all of these hold; otherwise
        the canonical form is the per-instance identity token inherited from
        :class:`~pirn.connectors.connector_base.ConnectorBase`:

        * its own class (not a base) defines :meth:`content_identity`;
        * the class has a unique, process-independent name
          (:class:`~pirn_agents.tools.definition_reference.DefinitionReference`),
          so a factory-built ``<locals>`` class, a shadowed class or a file-less
          ``__main__`` class stays identity-keyed;
        * :meth:`content_identity` returns a mapping, not ``None``.

        The content form is a type tag, the class reference and the declared config.
        The class is included because it fixes the wire format, completions path and
        any class-level headers. The tag keeps a provider's form from coinciding with
        an ordinary mapping value that happens to have the same two keys. No credential, header value, userinfo or query string
        ever appears in it. :meth:`_pirn_audit_dict` is unchanged.
        """
        provider_type = type(self)
        if "content_identity" not in vars(provider_type):
            return super().__pirn_canonical__()
        reference = DefinitionReference.of(provider_type)
        if reference is None:
            return super().__pirn_canonical__()
        config = self.content_identity()
        if config is None:
            return super().__pirn_canonical__()
        return {"__pirn_type__": "llm_provider", "provider": reference, "config": config}

    @staticmethod
    def _pricing_identity(pricing: ModelPricing) -> dict[str, float] | None:
        """Return the price sheet's fields, or ``None`` if it cannot be named.

        Only an exact :class:`ModelPricing` with plain numeric prices is named; a
        subclass may estimate cost differently from what its fields say.
        """
        if type(pricing) is not ModelPricing:
            return None
        fields = {
            "input_per_million": pricing.input_per_million,
            "output_per_million": pricing.output_per_million,
            "cached_input_per_million": pricing.cached_input_per_million,
        }
        if not all(BaseLLMProvider._is_plain_number(value) for value in fields.values()):
            return None
        return fields

    @staticmethod
    def _retry_policy_identity(policy: RetryPolicy) -> dict[str, float | int | bool] | None:
        """Return the retry policy's fields, or ``None`` if it cannot be named.

        Only an exact :class:`RetryPolicy` with plain values is named; a subclass may
        back off or give up differently from what its fields say.
        """
        if type(policy) is not RetryPolicy:
            return None
        numbers = {
            "max_retries": policy.max_retries,
            "base_delay": policy.base_delay,
            "max_delay": policy.max_delay,
            "multiplier": policy.multiplier,
            "max_retry_after": policy.max_retry_after,
        }
        if not all(BaseLLMProvider._is_plain_number(value) for value in numbers.values()):
            return None
        if not isinstance(policy.jitter, bool):
            return None
        return {**numbers, "jitter": policy.jitter}

    @staticmethod
    def _is_plain_int(value: object) -> bool:
        """Return whether ``value`` is an ``int`` (not a ``bool`` or other subclass)."""
        return type(value) is int

    @staticmethod
    def _is_plain_number(value: object) -> bool:
        """Return whether ``value`` is exactly an ``int`` or ``float``."""
        return type(value) in (int, float)

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

    # -- multimodal (F15-S2) capability surface -------------------------

    def modality_capability(self) -> ModalityCapability:
        """Return which content-block modalities this provider can encode.

        Delegates to the provider's multimodal adapter; a bare base provider
        that supplies no adapter is text-only, so an empty capability (text
        implicit, no image/audio/file) is returned.
        """
        adapter = self._multimodal_adapter()
        return adapter.capability() if adapter is not None else ModalityCapability()

    def encode_content(
        self, blocks: Sequence[ContentBlock], *, degrade: bool = False
    ) -> list[dict[str, Any]]:
        """Encode neutral content ``blocks`` into this provider's native parts.

        Providers with a multimodal adapter delegate to it (capability-gated,
        per-format shaping). A text-only base provider accepts text blocks and,
        with ``degrade=True``, projects any non-text block to a text part; else
        an unsupported block raises.

        Raises:
            UnsupportedModalityError: If a non-text block is present, this is a
                text-only provider, and ``degrade`` is ``False``.
        """
        adapter = self._multimodal_adapter()
        if adapter is not None:
            return adapter.encode_blocks(blocks, degrade=degrade)
        parts: list[dict[str, Any]] = []
        for block in blocks:
            if block.modality == "text":
                parts.append({"type": "text", "text": block.as_text})
            elif degrade:
                text = block.as_text or f"[{block.modality} content omitted]"
                parts.append({"type": "text", "text": text})
            else:
                raise UnsupportedModalityError(block.modality, type(self).__name__)
        return parts

    def decode_content(self, native_content: Any) -> tuple[ContentBlock, ...]:
        """Decode a provider-native content value back into neutral blocks.

        Providers with a multimodal adapter delegate to it; a text-only base
        provider returns a single text block (string input) or nothing.
        """
        adapter = self._multimodal_adapter()
        if adapter is not None:
            return adapter.decode_blocks(native_content)
        if isinstance(native_content, str):
            from pirn_agents.types.content.text_block import TextBlock

            return (TextBlock(text=native_content),)
        return ()

    def _multimodal_adapter(self) -> MultimodalAdapter | None:
        """Return this provider's multimodal adapter, or ``None`` if text-only.

        The base is text-only and returns ``None``; providers whose wire format
        carries media override this to return their adapter.
        """
        return None

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
        into decodable :class:`~pirn_agents.tools.tool_call.ToolCall`s via
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
        return AgentResponse(
            content="".join(content_parts),
            tool_calls=calls,
            finish_reason=finish_reason,
            usage=usage,
            cost=self._mapper.estimate_cost(usage),
        )

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
