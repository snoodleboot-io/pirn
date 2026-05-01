"""Connection pool wrapper around the synchronous BigQuery client.

The official ``google-cloud-bigquery`` library is synchronous; calls run in
a worker thread via :func:`asyncio.to_thread` so the connector cooperates
with pirn's async runtime without blocking the event loop on long jobs.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Iterable

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases._bigquery_stub_job_config import (
    BigqueryStubJobConfig,
)
from pirn.domains.connectors.databases.bigquery_config import BigqueryConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


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
        self._inline_param_re = re.compile(r"\{[^}]*\}|%[sd]")
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

        def _run() -> Any:
            job = client.query(query, job_config=job_config)
            return job.result()

        return await asyncio.to_thread(_run)

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        """Run a parameterised SELECT and return all rows as tuples."""
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        job_config = self._build_job_config(parameters)

        def _run() -> list[tuple[Any, ...]]:
            job = client.query(query, job_config=job_config)
            return [tuple(r) for r in job.result()]

        return await asyncio.to_thread(_run)

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> None:
        """Run the same statement once per parameter row."""
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        rows = [list(p) for p in parameter_seq]

        def _run() -> None:
            for params in rows:
                job_config = self._build_job_config(params)
                job = client.query(query, job_config=job_config)
                job.result()

        await asyncio.to_thread(_run)

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
            from google.cloud import bigquery  # type: ignore[import-not-found]
        except ImportError:
            bigquery = None  # type: ignore[assignment]

        wrapped: list[Any] = []
        if bigquery is not None:
            for value in params_list:
                if hasattr(value, "to_api_repr"):
                    wrapped.append(value)
                else:
                    wrapped.append(
                        bigquery.ScalarQueryParameter(
                            None, self._guess_bq_type(value), value
                        )
                    )
            return bigquery.QueryJobConfig(query_parameters=wrapped)
        # When the SDK is not installed (e.g. stub-injected client tests),
        # surface a plain object so the stub can introspect it without
        # needing the real BigQuery types.
        return BigqueryStubJobConfig(query_parameters=params_list)

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

    def _reject_inline_interpolation(self, query: str) -> None:
        if self._inline_param_re.search(query):
            raise ValueError(
                "BigqueryPool: query contains '{...}' or '%s' interpolation "
                "markers. Use named parameters via QueryJobConfig and pass "
                "values separately."
            )

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("BigqueryPool is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from google.cloud import bigquery  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "BigqueryPool requires google-cloud-bigquery; install via "
                "`pip install pirn[bigquery]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "BigqueryPool: missing config and no injected client"
            )

        kwargs: dict[str, Any] = {"location": self._config.location}
        if self._config.project_id is not None:
            kwargs["project"] = self._config.project_id
        try:
            if self._config.credentials_path:
                from google.oauth2 import (  # type: ignore[import-not-found]
                    service_account,
                )

                credentials = await asyncio.to_thread(
                    service_account.Credentials.from_service_account_file,
                    self._config.credentials_path,
                )
                kwargs["credentials"] = credentials
            client = await asyncio.to_thread(bigquery.Client, **kwargs)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("bigquery.connect")
        return client
