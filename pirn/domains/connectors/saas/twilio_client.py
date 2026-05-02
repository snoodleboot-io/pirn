"""Async ``ApiClient`` wrapper around the synchronous Twilio SDK.

``twilio.rest.Client`` is sync; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on slow Twilio calls.

The connector exposes:

1. **Vendor-typed methods** (:meth:`send_sms`).
2. The :class:`RecordWriter` capability — :meth:`write_records`
   forwards each record to ``send_sms`` and returns the count
   accepted.
3. The legacy :meth:`request` escape hatch.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.record_writer import RecordWriter
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.twilio_config import TwilioConfig


class TwilioClient(ApiClient, RecordWriter):
    """Concrete :class:`ApiClient` backed by the Twilio Python SDK.

    The Twilio :class:`Client` exposes a low-level
    ``request(method, uri, params=..., data=..., headers=...)`` used for
    the generic :meth:`request` interface. Tests inject a stub client
    that mirrors that surface.
    """

    def __init__(
        self,
        config: TwilioConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("TwilioClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> TwilioConfig | None:
        return self._config

    async def send_sms(
        self,
        *,
        from_number: str,
        to: str,
        body: str,
    ) -> Any:
        """Vendor-typed send — POST a single SMS to Twilio.

        Returns the underlying Twilio response (whatever the SDK
        produces for the POST against ``/Accounts/{sid}/Messages.json``).
        """
        if not isinstance(from_number, str) or not from_number:
            raise ValueError(
                "TwilioClient.send_sms: from_number must be a non-empty string"
            )
        if not isinstance(to, str) or not to:
            raise ValueError(
                "TwilioClient.send_sms: to must be a non-empty string"
            )
        if not isinstance(body, str) or not body:
            raise ValueError(
                "TwilioClient.send_sms: body must be a non-empty string"
            )
        path = self._messages_path()
        return await self.request(
            "POST",
            path,
            body={"From": from_number, "To": to, "Body": body},
        )

    async def write_records(
        self,
        records: Iterable[Mapping[str, Any]],
    ) -> int:
        """Send each record as an SMS via :meth:`send_sms`.

        Each record requires ``from``, ``to``, ``body`` keys (the
        capability-side spelling). Returns the number of messages
        successfully sent.
        """
        materialised = list(records)
        sent = 0
        for record in materialised:
            if "from" not in record or "to" not in record or "body" not in record:
                raise ValueError(
                    "TwilioClient.write_records: each record requires "
                    "'from', 'to', and 'body' keys"
                )
            await self.send_sms(
                from_number=record["from"],
                to=record["to"],
                body=record["body"],
            )
            sent += 1
        return sent

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        client = await self._ensure_client()
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None
        request_headers = dict(headers) if headers is not None else None

        def _run() -> Any:
            return client.request(
                method,
                path,
                params=request_params,
                data=request_body,
                headers=request_headers,
            )

        try:
            return await asyncio.to_thread(_run)
        except Exception as exc:
            self._reraise_scrubbed(exc)

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("twilio.close")

    def _messages_path(self) -> str:
        sid = (
            self._config.account_sid
            if self._config is not None
            else None
        )
        if sid is None:
            sid = "Account"
        return f"/2010-04-01/Accounts/{sid}/Messages.json"

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("TwilioClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from twilio.rest import Client  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "TwilioClient requires the twilio SDK; install via "
                "`pip install pirn[twilio]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "TwilioClient: missing config and no injected client"
            )

        kwargs: dict[str, Any] = {}
        if self._config.region is not None:
            kwargs["region"] = self._config.region

        try:
            client = await asyncio.to_thread(
                Client,
                self._config.account_sid,
                self._config.auth_token,
                **kwargs,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("twilio.connect")
        return client
