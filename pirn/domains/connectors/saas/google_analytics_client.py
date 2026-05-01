"""Google Analytics 4 Data API connector wrapping the sync ``BetaAnalyticsDataClient``.

The official ``google-analytics-data`` SDK is synchronous; calls run in a
worker thread via :func:`asyncio.to_thread` so the connector cooperates
with pirn's async runtime without blocking the event loop. The generic
:meth:`request` interface dispatches based on ``path`` to the matching
SDK method (``run_report``, ``run_realtime_report``, ...). Pagination,
when needed, is the caller's responsibility and is expressed by reissuing
``request`` with the appropriate offset / page token in ``body``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.google_analytics_config import (
    GoogleAnalyticsConfig,
)


class GoogleAnalyticsClient(ApiClient):
    """Async wrapper over a sync ``BetaAnalyticsDataClient``."""

    def __init__(
        self,
        config: GoogleAnalyticsConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "GoogleAnalyticsClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> GoogleAnalyticsConfig | None:
        return self._config

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        if not isinstance(method, str) or not method:
            raise ValueError(
                "GoogleAnalyticsClient.request: method must be non-empty"
            )
        if not isinstance(path, str) or not path:
            raise ValueError(
                "GoogleAnalyticsClient.request: path must be non-empty"
            )
        request_body: dict[str, Any] = dict(body) if body is not None else {}
        operation = self._resolve_operation(path)
        client = await self._ensure_client()

        def _run() -> Any:
            sdk_method = getattr(client, operation)
            return sdk_method(request_body)

        return await asyncio.to_thread(_run)

    async def close(self) -> None:
        if self._client is not None:
            transport = getattr(self._client, "transport", None)
            transport_close = getattr(transport, "close", None)
            client_close = getattr(self._client, "close", None)
            if callable(transport_close):
                await asyncio.to_thread(transport_close)
            elif callable(client_close):
                await asyncio.to_thread(client_close)
            self._client = None
        self._closed = True
        self._logger.debug("google_analytics.close")

    @staticmethod
    def _resolve_operation(path: str) -> str:
        normalised = path.lstrip("/")
        mapping = {
            "runReport": "run_report",
            "runRealtimeReport": "run_realtime_report",
            "runPivotReport": "run_pivot_report",
            "batchRunReports": "batch_run_reports",
            "batchRunPivotReports": "batch_run_pivot_reports",
        }
        if normalised not in mapping:
            supported = ", ".join(sorted(mapping))
            raise ValueError(
                "GoogleAnalyticsClient.request: unsupported path "
                f"{path!r}; supported: {supported}"
            )
        return mapping[normalised]

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("GoogleAnalyticsClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from google.analytics.data_v1beta import (  # type: ignore[import-not-found]
                BetaAnalyticsDataClient,
            )
        except ImportError as exc:
            raise ImportError(
                "GoogleAnalyticsClient requires google-analytics-data; install "
                "via `pip install pirn[google-analytics]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "GoogleAnalyticsClient: missing config and no injected client"
            )

        kwargs: dict[str, Any] = {}
        if self._config.service_account_json is not None:
            try:
                from google.oauth2 import (  # type: ignore[import-not-found]
                    service_account,
                )
            except ImportError as exc:
                raise ImportError(
                    "GoogleAnalyticsClient requires google-auth; install via "
                    "`pip install pirn[google-analytics]`"
                ) from exc
            info = json.loads(self._config.service_account_json)
            kwargs["credentials"] = (
                service_account.Credentials.from_service_account_info(info)
            )
        try:
            client = await asyncio.to_thread(
                BetaAnalyticsDataClient, **kwargs
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("google_analytics.connect")
        return client
