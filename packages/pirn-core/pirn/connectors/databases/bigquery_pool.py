"""Connection pool wrapper around the synchronous BigQuery client.

The official ``google-cloud-bigquery`` library is synchronous; calls run in
a worker thread via :func:`asyncio.to_thread` so the connector cooperates
with pirn's async runtime without blocking the event loop on long jobs.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases._bigquery_stub_job_config import (
    BigqueryStubJobConfig,
)
from pirn.connectors.databases.bigquery_config import BigqueryConfig
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.core.optional_dependency import OptionalDependency


class BigqueryPool(DatabaseConnectionPool):
    """Async-friendly wrapper around a single BigQuery client.

    BigQuery clients are stateless query dispatchers; ``acquire`` returns
    the same shared client and ``release`` is a no-op. ``execute`` and
    ``fetch_all`` use ``Client.query()`` with parameterised
    :class:`google.cloud.bigquery.QueryJobConfig`.
    """

    def __init__(
        self,
        config: BigqueryConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("BigqueryPool requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> BigqueryConfig | None:
        return self._config

    async def acquire(self) -> Any:
        return await self._ensure_client()

    async def release(self, connection: Any) -> None:
        return None  # BigQuery client is shared and stateless.

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("bigquery.close")

    async def execute(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> Any:
        """Run a parameterised statement and wait for completion."""
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        job_config = self._build_job_config(parameters)
        return await asyncio.to_thread(self._sync_execute, client, query, job_config)

    @staticmethod
    def _sync_execute(client: Any, query: str, job_config: Any) -> Any:
        job = client.query(query, job_config=job_config)
        return job.result()

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        """Run a parameterised SELECT and return all rows as tuples."""
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        job_config = self._build_job_config(parameters)
        return await asyncio.to_thread(self._sync_fetch_all, client, query, job_config)

    @staticmethod
    def _sync_fetch_all(client: Any, query: str, job_config: Any) -> list[tuple[Any, ...]]:
        job = client.query(query, job_config=job_config)
        return [tuple(r) for r in job.result()]

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> None:
        """Run the same statement once per parameter row."""
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        rows = [list(p) for p in parameter_seq]
        await asyncio.to_thread(self._sync_execute_many, client, query, rows)

    def _sync_execute_many(self, client: Any, query: str, rows: list[Any]) -> None:
        for params in rows:
            job_config = self._build_job_config(params)
            job = client.query(query, job_config=job_config)
            job.result()

    def _build_job_config(self, parameters: Iterable[Any] | None) -> Any:
        """Construct a ``QueryJobConfig`` carrying positional parameters.

        BigQuery requires typed parameter objects. Parameters supplied as
        already-built ``ScalarQueryParameter``/``ArrayQueryParameter``
        instances pass through unchanged; bare Python values are wrapped
        with a best-effort type guess.
        """
        if parameters is None:
            params_list: list[Any] = []
        else:
            params_list = list(parameters)
        try:
            bigquery = OptionalDependency.require("google.cloud.bigquery", extra="bigquery")
        except ImportError:
            # When the SDK is not installed (e.g. stub-injected client tests),
            # surface a plain object so the stub can introspect it without
            # needing the real BigQuery types.
            return BigqueryStubJobConfig(query_parameters=params_list)

        wrapped: list[Any] = []
        for value in params_list:
            if hasattr(value, "to_api_repr"):
                wrapped.append(value)
            else:
                wrapped.append(
                    bigquery.ScalarQueryParameter(None, self._guess_bq_type(value), value)
                )
        return bigquery.QueryJobConfig(query_parameters=wrapped)

    @staticmethod
    def _guess_bq_type(value: Any) -> str:
        if isinstance(value, bool):
            return "BOOL"
        if isinstance(value, int):
            return "INT64"
        if isinstance(value, float):
            return "FLOAT64"
        if isinstance(value, bytes):
            return "BYTES"
        return "STRING"

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise self._closed_error("BigqueryPool")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        bigquery = OptionalDependency.require("google.cloud.bigquery", extra="bigquery")
        if self._config is None:
            raise self._missing_config_error("BigqueryPool", "client")

        kwargs: dict[str, Any] = {"location": self._config.location}
        if self._config.project_id is not None:
            kwargs["project"] = self._config.project_id
        try:
            if self._config.credentials_path:
                service_account = OptionalDependency.require(
                    "google.oauth2.service_account", extra="bigquery"
                )
                credentials = await asyncio.to_thread(
                    service_account.Credentials.from_service_account_file,
                    self._config.credentials_path,
                )
                kwargs["credentials"] = credentials
            client: Any = await asyncio.to_thread(bigquery.Client, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("bigquery.connect")
        return client
