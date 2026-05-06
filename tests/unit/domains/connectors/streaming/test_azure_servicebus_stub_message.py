"""Tests for :class:`AzureServiceBusStubMessage`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.streaming.azure_servicebus_stub_message import (
    AzureServiceBusStubMessage,
)


class TestAzureServiceBusStubMessage(unittest.TestCase):
    def test_body_stored(self) -> None:
        msg = AzureServiceBusStubMessage(body=b"hello", key=None, headers=None)
        self.assertEqual(msg.body, b"hello")

    def test_key_decoded_to_session_id(self) -> None:
        msg = AzureServiceBusStubMessage(body=b"x", key=b"session-1", headers=None)
        self.assertEqual(msg.session_id, "session-1")

    def test_key_none_gives_none_session_id(self) -> None:
        msg = AzureServiceBusStubMessage(body=b"x", key=None, headers=None)
        self.assertIsNone(msg.session_id)

    def test_headers_stored_as_application_properties(self) -> None:
        msg = AzureServiceBusStubMessage(
            body=b"x", key=None, headers={"x-trace": b"abc"}
        )
        self.assertEqual(msg.application_properties, {"x-trace": b"abc"})

    def test_none_headers_give_none_application_properties(self) -> None:
        msg = AzureServiceBusStubMessage(body=b"x", key=None, headers=None)
        self.assertIsNone(msg.application_properties)
