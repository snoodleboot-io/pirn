"""Airtable connector wrapping the REST API v0 via ``httpx``.

Exposes:

1. **Vendor-typed methods**: :meth:`list_records`, :meth:`create_record`,
   :meth:`update_record`, :meth:`delete_record`.
2. The :class:`TableSource` capability via :meth:`fetch_page`.
3. The generic :meth:`request` escape hatch.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.capabilities.table_source import TableSource
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.saas.airtable_config import AirtableConfig


class AirtableClient(ApiClient, TableSource):
    """Async Airtable REST API v0 client backed by ``httpx``."""

    _base_url: str = "https://api.airtable.com"

    def __init__(
        self,
        config: AirtableConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("AirtableClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> AirtableConfig | None:
        return self._config

    async def list_records(
        self,
        *,
        offset: str | None = None,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """List records from the configured table.

        Parameters
        ----------
        offset:
            Pagination offset token returned by a previous call.
        page_size:
            Number of records per page (overrides config default).

        Returns
        -------
        ``(records, next_offset)`` where ``next_offset=None`` signals the
        last page.
        """
        self._validate_config()
        params: dict[str, Any] = {}
        if offset is not None:
            params["offset"] = offset
        effective_page_size = page_size
        if effective_page_size is None and self._config is not None:
            effective_page_size = self._config.page_size
        if effective_page_size is not None:
            params["pageSize"] = effective_page_size

        path = self._table_path()
        self._logger.debug("airtable.list_records path=%s", path)
        response = await self.request("GET", path, params=params or None)
        if "records" not in response:
            raise ValueError(
                f"AirtableClient: response missing required field 'records'; got: {list(response)}"
            )
        records: list[Mapping[str, Any]] = list(response["records"])
        # offset is an optional pagination cursor; absent means last page
        next_offset = response.get("offset") or None
        return records, next_offset

    async def create_record(self, fields: dict) -> dict:
        """Create a new record in the configured table.

        Parameters
        ----------
        fields:
            Dict of field name to value for the new record.
        """
        self._validate_config()
        path = self._table_path()
        self._logger.debug("airtable.create_record path=%s", path)
        response = await self.request("POST", path, body={"fields": fields})
        return dict(response)

    async def update_record(self, record_id: str, fields: dict) -> dict:
        """Patch an existing record in the configured table.

        Parameters
        ----------
        record_id:
            The Airtable record ID (``recXXXXXXXXXXXXXX``).
        fields:
            Fields to update.
        """
        self._validate_config()
        path = f"{self._table_path()}/{record_id}"
        self._logger.debug("airtable.update_record record_id=%s", record_id)
        response = await self.request("PATCH", path, body={"fields": fields})
        return dict(response)

    async def delete_record(self, record_id: str) -> dict:
        """Delete a record from the configured table.

        Parameters
        ----------
        record_id:
            The Airtable record ID to delete.
        """
        self._validate_config()
        path = f"{self._table_path()}/{record_id}"
        self._logger.debug("airtable.delete_record record_id=%s", record_id)
        response = await self.request("DELETE", path)
        return dict(response)

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — delegates to :meth:`list_records`."""
        return await self.list_records(offset=cursor, page_size=page_size)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Generic escape hatch — authenticated httpx call to the Airtable API."""
        client = await self._ensure_client()
        url = f"{self._base_url}{path}"
        api_key = self._api_key()
        merged_headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if headers is not None:
            merged_headers.update(headers)
        self._logger.debug("airtable.request method=%s path=%s", method, path)
        response = await client.request(
            method,
            url,
            params=dict(params) if params is not None else None,
            json=dict(body) if body is not None else None,
            headers=merged_headers,
        )
        return response

    def _table_path(self) -> str:
        if self._config is None:
            raise RuntimeError("AirtableClient: config is required to derive table path")
        return f"/v0/{self._config.base_id}/{self._config.table_name}"

    def _api_key(self) -> str:
        if self._config is not None and self._config.api_key:
            return self._config.api_key
        raise RuntimeError("AirtableClient: api_key is required")

    def _validate_config(self) -> None:
        if self._closed:
            raise RuntimeError("AirtableClient is closed")
        if self._config is None:
            return
        missing = [
            field
            for field in ("api_key", "base_id", "table_name")
            if not getattr(self._config, field)
        ]
        if missing:
            raise ValueError(f"AirtableConfig: the following fields must be non-empty: {missing}")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("airtable.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("AirtableClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "AirtableClient requires httpx; install via pip install pirn[airtable]"
            ) from exc
        if self._config is None:
            raise RuntimeError("AirtableClient: missing config and no injected client")
        self._validate_config()
        self._logger.debug("airtable.connect")
        return httpx.AsyncClient(timeout=self._config.timeout)
