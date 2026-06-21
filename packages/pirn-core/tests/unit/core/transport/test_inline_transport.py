"""Unit tests for :class:`InlineTransport`."""

from __future__ import annotations

import logging
import unittest

from pirn.core.transport.inline_transport import InlineTransport
from pirn.core.transport.transport_handle import TransportHandle


class TestInlineTransport(unittest.IsolatedAsyncioTestCase):
    async def test_transport_id(self) -> None:
        t = InlineTransport()
        assert t.transport_id == "inline"

    async def test_write_returns_handle_with_inline_value(self) -> None:
        t = InlineTransport()
        await t.begin_run("run-1")
        value = {"patient_id": "P1", "score": 0.9}
        handle = await t.write("run-1", "scorer", value)
        assert isinstance(handle, TransportHandle)
        assert handle._inline_value is value
        assert handle.transport_id == "inline"

    async def test_read_returns_exact_value(self) -> None:
        t = InlineTransport()
        await t.begin_run("run-1")
        value = [1, 2, 3]
        handle = await t.write("run-1", "knot-a", value)
        result = await t.read(handle)
        assert result is value

    async def test_exists_true_for_written_handle(self) -> None:
        t = InlineTransport()
        await t.begin_run("run-1")
        handle = await t.write("run-1", "k", {"x": 1})
        assert await t.exists(handle)

    async def test_exists_false_for_none_inline_value(self) -> None:
        t = InlineTransport()
        handle = TransportHandle(
            transport_id="inline", key="", type_name="NoneType", _inline_value=None
        )
        assert not await t.exists(handle)

    async def test_end_run_is_noop(self) -> None:
        t = InlineTransport()
        await t.begin_run("run-1")
        await t.end_run("run-1", success=True)

    async def test_type_name_recorded_in_handle(self) -> None:
        t = InlineTransport()
        await t.begin_run("run-1")
        handle = await t.write("run-1", "k", {"a": 1})
        assert "dict" in handle.type_name

    async def test_size_warning_emitted_once_per_knot(self) -> None:
        t = InlineTransport(warn_above_bytes=1)
        await t.begin_run("run-1")
        with self.assertLogs("pirn.core.transport.inline_transport", level=logging.WARNING) as cm:
            await t.write("run-1", "big-knot", "x" * 100)
            await t.write("run-1", "big-knot", "x" * 100)
        assert len([m for m in cm.output if "big-knot" in m]) == 1

    async def test_no_warning_for_small_values(self) -> None:
        t = InlineTransport(warn_above_bytes=10 * 1024 * 1024)
        await t.begin_run("run-1")
        with self.assertNoLogs("pirn.core.transport.inline_transport", level=logging.WARNING):
            await t.write("run-1", "small-knot", {"x": 1})
