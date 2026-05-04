"""PagerDuty connector via ``httpx``.

Exposes:

1. **Vendor-typed methods**: :meth:`trigger_incident`, :meth:`resolve_incident`,
   :meth:`list_incidents`.
2. The generic :meth:`request` escape hatch.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.messaging.pagerduty_config import PagerDutyConfig


_VALID_SEVERITIES: frozenset[str] = frozenset({"critical", "error", "warning", "info"})

_EVENTS_API_URL: str = "https://events.pagerduty.com/v2/enqueue"


class PagerDutyClient(ApiClient):
    """Async PagerDuty client backed by ``httpx``."""

    def __init__(
        self,
        config: PagerDutyConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("PagerDutyClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> PagerDutyConfig | None:
        return self._config

    async def trigger_incident(
        self,
        summary: str,
        source: str,
        *,
        severity: str = "error",
        dedup_key: str | None = None,
    ) -> dict:
        """Trigger an incident via the PagerDuty Events API v2.

        Parameters
        ----------
        summary:
            Human-readable description of the event.
        source:
            The affected system or service.
        severity:
            One of ``"critical"``, ``"error"``, ``"warning"``, ``"info"``.
        dedup_key:
            Optional deduplication key for event grouping.
        """
        if severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"PagerDutyClient: severity must be one of "
                f"{sorted(_VALID_SEVERITIES)!r}; got {severity!r}"
            )
        routing_key = self._routing_key()
        payload: dict[str, Any] = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": summary,
                "source": source,
                "severity": severity,
            },
        }
        if dedup_key is not None:
            payload["dedup_key"] = dedup_key
        self._logger.debug("pagerduty.trigger_incident summary=%s", summary)
        return await self._post_events(payload)

    async def resolve_incident(self, dedup_key: str) -> dict:
        """Resolve an incident via the PagerDuty Events API v2.

        Parameters
        ----------
        dedup_key:
            Deduplication key identifying the incident to resolve.
        """
        routing_key = self._routing_key()
        payload: dict[str, Any] = {
            "routing_key": routing_key,
            "event_action": "resolve",
            "dedup_key": dedup_key,
        }
        self._logger.debug("pagerduty.resolve_incident dedup_key=%s", dedup_key)
        return await self._post_events(payload)

    async def list_incidents(
        self,
        *,
        status: str = "triggered",
        limit: int = 25,
    ) -> list[dict]:
        """List incidents from the PagerDuty REST API.

        Parameters
        ----------
        status:
            Filter by incident status (e.g. ``"triggered"``, ``"acknowledged"``).
        limit:
            Maximum number of incidents to return.
        """
        self._logger.debug("pagerduty.list_incidents status=%s", status)
        response = await self.request(
            "GET",
            "/incidents",
            params={"statuses[]": status, "limit": limit},
        )
        return list(response.get("incidents") or ())

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Generic escape hatch — authenticated httpx call to the REST API."""
        client = await self._ensure_client()
        base_url = self._config.base_url if self._config is not None else "https://api.pagerduty.com"
        url = f"{base_url}{path}"
        api_key = self._api_key()
        merged_headers: dict[str, str] = {
            "Authorization": f"Token token={api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
        }
        if headers is not None:
            merged_headers.update(headers)
        self._logger.debug("pagerduty.request method=%s path=%s", method, path)
        response = await client.request(
            method,
            url,
            params=dict(params) if params is not None else None,
            json=dict(body) if body is not None else None,
            headers=merged_headers,
        )
        return response

    async def _post_events(self, payload: dict) -> dict:
        client = await self._ensure_client()
        self._logger.debug("pagerduty._post_events")
        response = await client.post(_EVENTS_API_URL, json=payload)
        return dict(response)

    def _routing_key(self) -> str:
        if self._config is not None and self._config.routing_key:
            return self._config.routing_key
        raise RuntimeError("PagerDutyClient: routing_key is required for Events API calls")

    def _api_key(self) -> str:
        if self._config is not None and self._config.api_key:
            return self._config.api_key
        raise RuntimeError("PagerDutyClient: api_key is required for REST API calls")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("pagerduty.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("PagerDutyClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "PagerDutyClient requires httpx; install via pip install pirn[pagerduty]"
            ) from exc
        if self._config is None:
            raise RuntimeError("PagerDutyClient: missing config and no injected client")
        if not self._config.api_key:
            raise ValueError("PagerDutyClient: config.api_key must be non-empty")
        self._logger.debug("pagerduty.connect")
        return httpx.AsyncClient(timeout=self._config.timeout)
