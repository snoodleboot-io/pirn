"""Tests for :class:`PandasCast`."""

from __future__ import annotations

import unittest

try:
    import pandas  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pandas not installed") from _e

import pandas as pd

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.frames.pandas.pandas_cast import PandasCast
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch
from pirn.tapestry import Tapestry


@knot
async def emit_string_columns() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame({"id": ["1", "2"], "amount": ["12.5", "99.0"]})
    )


def _string_batch() -> PandasDataBatch:
    return PandasDataBatch(
        frame=pd.DataFrame({"id": ["1", "2"], "amount": ["12.5", "99.0"]})
    )


class TestPandasCast(unittest.IsolatedAsyncioTestCase):
    async def test_python_primitives_are_translated_to_pandas_dtypes(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PandasCast(
                batch=batch,
                casts={"id": int, "amount": float},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["casted"]
        assert str(out.frame["id"].dtype) == "int64"
        assert str(out.frame["amount"].dtype) == "float64"

    async def test_dtype_string_passes_through(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PandasCast(
                batch=batch,
                casts={"id": "int32"},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["casted"]
        assert str(out.frame["id"].dtype) == "int32"

    async def test_columns_not_in_frame_are_skipped(self) -> None:
        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            PandasCast(
                batch=batch,
                casts={"absent": int},
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["casted"]
        # No-op; original dtypes preserved (object in pandas <2, StringDtype in pandas 3+).
        assert pd.api.types.is_string_dtype(out.frame["id"])


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_casts_from_upstream_knot(self) -> None:
        @knot
        async def emit_casts() -> object:
            return {"id": int}

        with Tapestry() as t:
            batch = emit_string_columns(_config=KnotConfig(id="users"))
            casts_knot = emit_casts(_config=KnotConfig(id="casts"))
            PandasCast(
                batch=batch,
                casts=casts_knot,
                _config=KnotConfig(id="casted"),
            )
        result = await t.run(RunRequest())
        out: PandasDataBatch = result.outputs["casted"]
        assert str(out.frame["id"].dtype) == "int64"


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> PandasCast:
        @knot
        async def empty() -> PandasDataBatch:
            return PandasDataBatch(frame=pd.DataFrame())

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return PandasCast(
                batch=batch,
                casts={"id": int},
                _config=KnotConfig(id="c"),
                **kwargs,
            )

    async def test_rejects_unknown_dtype_kind(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "Pandas dtype"):
            await k.process(
                batch=_string_batch(),
                casts={"id": 123},
            )

    async def test_rejects_empty_casts(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(
                batch=_string_batch(),
                casts={},
            )

    async def test_rejects_non_string_key(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "non-empty strings"):
            await k.process(
                batch=_string_batch(),
                casts={"": int},
            )
