"""Tests for :class:`ElandToPandas`.

Materialisation calls ``eland.eland_to_pandas`` which would issue a real
Elasticsearch query — we monkey-patch that function so the test runs
offline.
"""

from __future__ import annotations

from typing import Any
import unittest

import pandas as pd

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame
from pirn.domains.data.specialized.eland.eland_to_pandas import ElandToPandas
from pirn.tapestry import Tapestry


class _FakeFrame:
    pass


class TestElandToPandas(unittest.IsolatedAsyncioTestCase):
    async def test_materialises_via_stubbed_eland_to_pandas(self) -> None:
        try:
            import eland
        except ImportError as _e:
            self.skipTest("eland not installed")
        import eland as ed

        captured: dict[str, Any] = {}
        out_df = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})

        def fake_eland_to_pandas(frame: Any) -> pd.DataFrame:
            captured["frame"] = frame
            return out_df

        with unittest.mock.patch.object(ed, "eland_to_pandas", fake_eland_to_pandas):
            @knot
            async def emit() -> ElandDataFrame:
                return ElandDataFrame(frame=_FakeFrame(), source_uri="elasticsearch://x")

            with Tapestry() as t:
                up = emit(_config=KnotConfig(id="up"))
                ElandToPandas(frame=up, _config=KnotConfig(id="bridge"))
            result = await t.run(RunRequest())

        out = result.outputs["bridge"]
        assert isinstance(out, PandasDataBatch)
        assert list(out.frame["id"]) == [1, 2]
        # The eland frame was actually passed to eland_to_pandas.
        assert isinstance(captured["frame"], _FakeFrame)
        # Source URI carries through.
        assert out.source_uri == "elasticsearch://x"
