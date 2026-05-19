"""Tests for :class:`LanceToArrow`.

The conversion is delegated to ``LanceDataset.to_table()``; using a fake
that mimics that method exercises the knot without requiring pylance.
"""

from __future__ import annotations

import unittest

try:
    import pyarrow  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pyarrow not installed") from _e

try:
    import lance  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lance not installed") from _e

from typing import Any

import pyarrow as pa

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specialized.lance.lance_dataset import LanceDataset
from pirn.domains.data.specialized.lance.lance_to_arrow import LanceToArrow
from pirn.tapestry import Tapestry


class _FakeLanceDataset:
    def __init__(self, table: pa.Table) -> None:
        self._table = table

    def to_table(self) -> pa.Table:
        return self._table


class TestLanceToArrow(unittest.IsolatedAsyncioTestCase):
    async def test_emits_pyarrow_table_from_lance_dataset(self) -> None:
        table = pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})

        @knot
        async def emit() -> LanceDataset:
            return LanceDataset(dataset=_FakeLanceDataset(table))

        with Tapestry() as t:
            src = emit(_config=KnotConfig(id="src"))
            LanceToArrow(dataset=src, _config=KnotConfig(id="bridge"))

        result = await t.run(RunRequest())
        out: Any = result.outputs["bridge"]
        assert isinstance(out, pa.Table)
        assert out.num_rows == 3
        assert out.column_names == ["id", "name"]
