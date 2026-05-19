"""Tests for DualWriteTransport — fan-out writes, primary reads."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.core.transport.dual_write_transport import DualWriteTransport
from pirn.core.transport.inline_transport import InlineTransport
from pirn.core.transport.transport_error import TransportError
from pirn.core.transport.transport_handle import TransportHandle


def _handle(transport_id: str = "primary") -> TransportHandle:
    return TransportHandle(
        transport_id=transport_id, key="k", type_name="builtins.int", size_bytes=4, checksum="abc"
    )


def _mock_transport(tid: str) -> MagicMock:
    t = MagicMock(spec=InlineTransport)
    t.transport_id = tid
    t.begin_run = AsyncMock()
    t.end_run = AsyncMock()
    t.write = AsyncMock(return_value=_handle(tid))
    t.read = AsyncMock(return_value=42)
    t.exists = AsyncMock(return_value=True)
    return t


class TestDualWriteTransport(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_mirror_errors_raises(self) -> None:
        with self.assertRaises(ValueError):
            DualWriteTransport(
                primary=_mock_transport("p"),
                mirror=_mock_transport("m"),
                mirror_errors="bad",
            )

    async def test_transport_id_contains_both(self) -> None:
        d = DualWriteTransport(primary=_mock_transport("p"), mirror=_mock_transport("m"))
        assert "p" in d.transport_id
        assert "m" in d.transport_id

    async def test_begin_run_calls_both(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        d = DualWriteTransport(primary=p, mirror=m)
        await d.begin_run("r1")
        p.begin_run.assert_called_once_with("r1")
        m.begin_run.assert_called_once_with("r1")

    async def test_write_calls_both(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        d = DualWriteTransport(primary=p, mirror=m)
        await d.begin_run("r1")
        await d.write("r1", "k1", 99)
        p.write.assert_called_once_with("r1", "k1", 99)
        m.write.assert_called_once_with("r1", "k1", 99)

    async def test_write_returns_primary_handle(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        d = DualWriteTransport(primary=p, mirror=m)
        await d.begin_run("r1")
        handle = await d.write("r1", "k1", 99)
        assert handle.transport_id == "p"

    async def test_read_from_primary_only(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        d = DualWriteTransport(primary=p, mirror=m)
        await d.read(_handle("p"))
        p.read.assert_called_once()
        m.read.assert_not_called()

    async def test_exists_from_primary_only(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        d = DualWriteTransport(primary=p, mirror=m)
        await d.exists(_handle("p"))
        p.exists.assert_called_once()
        m.exists.assert_not_called()

    async def test_end_run_calls_both(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        d = DualWriteTransport(primary=p, mirror=m)
        await d.begin_run("r1")
        await d.end_run("r1", success=True)
        p.end_run.assert_called_once_with("r1", success=True)
        m.end_run.assert_called_once_with("r1", success=True)

    async def test_primary_write_failure_raises(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        p.write = AsyncMock(side_effect=RuntimeError("disk full"))
        d = DualWriteTransport(primary=p, mirror=m)
        await d.begin_run("r1")
        with self.assertRaises(RuntimeError, msg="disk full"):
            await d.write("r1", "k1", 1)

    async def test_mirror_write_failure_raises_by_default(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        m.write = AsyncMock(side_effect=RuntimeError("mirror down"))
        d = DualWriteTransport(primary=p, mirror=m)
        await d.begin_run("r1")
        with self.assertRaises(TransportError):
            await d.write("r1", "k1", 1)

    async def test_mirror_write_failure_warn_continues(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        m.write = AsyncMock(side_effect=RuntimeError("mirror down"))
        d = DualWriteTransport(primary=p, mirror=m, mirror_errors="warn")
        await d.begin_run("r1")
        handle = await d.write("r1", "k1", 1)
        assert handle.transport_id == "p"

    async def test_mirror_write_failure_ignore_continues(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        m.write = AsyncMock(side_effect=RuntimeError("mirror down"))
        d = DualWriteTransport(primary=p, mirror=m, mirror_errors="ignore")
        await d.begin_run("r1")
        handle = await d.write("r1", "k1", 1)
        assert handle.transport_id == "p"

    async def test_end_run_both_fail_raises_transport_error(self) -> None:
        p, m = _mock_transport("p"), _mock_transport("m")
        p.end_run = AsyncMock(side_effect=RuntimeError("p down"))
        m.end_run = AsyncMock(side_effect=RuntimeError("m down"))
        d = DualWriteTransport(primary=p, mirror=m)
        with self.assertRaises(TransportError):
            await d.end_run("r1", success=True)
