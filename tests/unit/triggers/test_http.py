"""Unit tests for WebhookTrigger."""

from __future__ import annotations

import asyncio
import unittest

from pirn.core.run_request import RunRequest
from pirn.triggers.http import WebhookTrigger


class TestWebhookTriggerConstruction(unittest.TestCase):
    def test_default_path(self) -> None:
        t = WebhookTrigger()
        self.assertEqual(t._path, "/run")

    def test_custom_path(self) -> None:
        t = WebhookTrigger(path="/webhook")
        self.assertEqual(t._path, "/webhook")

    def test_name(self) -> None:
        self.assertEqual(WebhookTrigger().name, "WebhookTrigger")

    def test_with_auth_token(self) -> None:
        t = WebhookTrigger(auth_token="secret")
        self.assertEqual(t._auth_token, "secret")

    def test_with_rate_limit(self) -> None:
        t = WebhookTrigger(rate_limit_rpm=60)
        self.assertEqual(t._rate_limit_rpm, 60)


class TestWebhookTriggerStream(unittest.IsolatedAsyncioTestCase):
    async def test_submit_yields_request(self) -> None:
        trigger = WebhookTrigger()
        req = RunRequest()

        received = []

        async def _consume() -> None:
            async for r in trigger.stream():
                received.append(r)

        task = asyncio.ensure_future(_consume())
        await asyncio.sleep(0)
        await trigger.submit(req)
        await trigger.close()
        await task
        self.assertIn(req, received)

    async def test_close_stops_stream(self) -> None:
        trigger = WebhookTrigger()
        await trigger.close()
        count = 0
        async for _ in trigger.stream():
            count += 1
        self.assertEqual(count, 0)

    async def test_default_request_builder_parses_dict(self) -> None:
        builder = WebhookTrigger._WebhookTrigger__default_request_builder
        req = builder({"x": 1}, None)
        self.assertIsInstance(req, RunRequest)
        self.assertEqual(req.parameters["x"], 1)

    async def test_default_request_builder_rejects_non_dict(self) -> None:
        builder = WebhookTrigger._WebhookTrigger__default_request_builder
        with self.assertRaises(TypeError):
            builder([1, 2, 3], None)

    async def test_handle_request_auth_token_required(self) -> None:
        trigger = WebhookTrigger(auth_token="my-secret")

        class FakeRequest:
            headers = {}
            client = None

            async def body(self):
                return b'{}'

        from starlette.responses import JSONResponse
        response = await trigger._handle_request(FakeRequest())
        self.assertEqual(response.status_code, 401)

    async def test_handle_request_valid_auth(self) -> None:
        trigger = WebhookTrigger(auth_token="my-secret")

        class FakeRequest:
            headers = {"Authorization": "Bearer my-secret"}
            client = None

            async def body(self):
                return b'{}'

        response = await trigger._handle_request(FakeRequest())
        self.assertEqual(response.status_code, 200)
