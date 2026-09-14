"""``LLMProviderIdentityMixin`` — content-identity + canonicalisation for HTTP LLM providers.

Extracted from :class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider` (PIR-856,
SRP) to keep that orchestrator under one screenful of responsibility. This mixin
owns the PIR-840 "does this provider replay across processes without a
credential?" surface: :meth:`content_identity`, the
:meth:`__pirn_canonical__` hook :meth:`pirn.core.content_hasher.ContentHasher.hash` reads,
and the private helpers that decide whether a collaborator's config can be
named safely.

It declares the host attributes it reads (set by
:class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider.__init__`) as bare
annotations so it type-checks stand-alone; it contributes no ``__init__`` of
its own and is always combined with that base, never instantiated directly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_retry_policy import KnotRetryPolicy

from pirn_agents.llm.endpoint_identity import EndpointIdentity
from pirn_agents.llm.http_transport import HttpTransport
from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.response_mapper import ResponseMapper
from pirn_agents.tools.definition_reference import DefinitionReference


class LLMProviderIdentityMixin:
    """Content-identity surface for :class:`BaseLLMProvider` (PIR-840)."""

    # -- host attributes this mixin reads (set by BaseLLMProvider.__init__) --
    _injected_client: Any | None
    _transport: HttpTransport
    _mapper: ResponseMapper
    _base_url: str
    _default_max_tokens: int | None
    _timeout: float
    _model: str
    _enable_prompt_cache: bool
    _retry_policy: KnotRetryPolicy

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
        """Return the form :meth:`pirn.core.content_hasher.ContentHasher.hash` hashes.

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
            return super().__pirn_canonical__()  # type: ignore[misc]
        reference = DefinitionReference.of(provider_type)
        if reference is None:
            return super().__pirn_canonical__()  # type: ignore[misc]
        config = self.content_identity()
        if config is None:
            return super().__pirn_canonical__()  # type: ignore[misc]
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
        if not all(LLMProviderIdentityMixin._is_plain_number(value) for value in fields.values()):
            return None
        return fields

    @staticmethod
    def _retry_policy_identity(policy: KnotRetryPolicy) -> dict[str, float | int | bool] | None:
        """Return the retry policy's fields, or ``None`` if it cannot be named.

        Only an exact :class:`KnotRetryPolicy` with plain values and no predicate
        is named; a subclass, or an ``is_retryable``/``retry_after`` callable, may
        back off or give up differently from what its fields say.
        """
        if type(policy) is not KnotRetryPolicy:
            return None
        if policy.is_retryable is not None or policy.retry_after is not None:
            return None
        numbers = {
            "max_attempts": policy.max_attempts,
            "base_delay": policy.base_delay,
            "max_delay": policy.max_delay,
            "multiplier": policy.multiplier,
            "max_retry_after": policy.max_retry_after,
        }
        if not all(LLMProviderIdentityMixin._is_plain_number(value) for value in numbers.values()):
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
