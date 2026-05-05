"""Tests for framework-level scalar-to-Parameter coercion.

When a knot's ``process`` declares a ``Knot | T`` union hint, passing a
plain scalar of type ``T`` at construction time should automatically be
wrapped in a ``Parameter`` node rather than silently becoming config.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional, Union
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry


# ------------------------------------------------------------------ fixtures


class StepRouter(Knot):
    async def process(self, step: Knot | str, **_: Any) -> str:
        return step


class MultiCoerceKnot(Knot):
    async def process(self, step: Knot | str, max_results: Knot | int, **_: Any) -> str:
        return f"{step}:{max_results}"


class TypingUnionRouter(Knot):
    async def process(self, step: Union[Knot, str], **_: Any) -> str:
        return step


class NullableInput(Knot):
    async def process(self, value: Knot | str | None, **_: Any) -> str:
        return value or ""


# ------------------------------------------------------------------ coercion detection



class _StandaloneTests(unittest.TestCase):
    def test_coercible_params_detected_on_class(self):
        coerce_type, adapter_type = StepRouter._coercible_params["step"]
        assert coerce_type is str
        assert adapter_type is str
    
    
    def test_coercible_params_int(self):
        coerce_type, adapter_type = MultiCoerceKnot._coercible_params["max_results"]
        assert coerce_type is int
        assert adapter_type is int
    
    
    def test_typing_union_also_detected(self):
        assert "step" in TypingUnionRouter._coercible_params
    
    
    def test_nullable_union_coercible(self):
        # Knot | str | None — coerce_type=str, adapter_type=str|None
        coerce_type, adapter_type = NullableInput._coercible_params["value"]
        assert coerce_type is str
        # adapter_type must accept None (Optional[str])
        from pydantic import TypeAdapter
        ta = TypeAdapter(adapter_type)
        assert ta.validate_python(None) is None
        assert ta.validate_python("hello") == "hello"
    
    
# ------------------------------------------------------------------ auto-wrap in tapestry


    def test_scalar_becomes_parameter_in_tapestry(self):
        with Tapestry() as t:
            router = StepRouter(
                step="lookup policy",
                _config=KnotConfig(id="router"),
            )
    
        assert "step" in router.parents
        auto_param = router.parents["step"]
        assert isinstance(auto_param, Parameter)
        assert auto_param.has_default
        assert auto_param.default == "lookup policy"
        assert "step" not in router.config_values
    
    
    def test_auto_parameter_registered_in_tapestry(self):
        with Tapestry() as t:
            router = StepRouter(step="lookup", _config=KnotConfig(id="router"))
    
        knot_ids = {k.knot_id for k in t._store.all()}
        assert any("router" in kid and "step" in kid for kid in knot_ids), (
            f"No auto-param id found in tapestry: {knot_ids}"
        )
    
    
    def test_knot_parent_not_re_wrapped(self):
        with Tapestry() as t:
            upstream = Parameter("q", str, _config=KnotConfig(id="q"))
            router = StepRouter(step=upstream, _config=KnotConfig(id="router"))
    
        assert router.parents["step"] is upstream
    
    
    def test_none_not_coerced(self):
        with Tapestry() as t:
            node = NullableInput(value=None, _config=KnotConfig(id="ni"))
    
        # None passes through as config, not wrapped
        assert "value" not in node.parents
        assert node.config_values.get("value") is None
    
    
# ------------------------------------------------------------------ runtime round-trip


    def test_coerced_scalar_value_flows_at_runtime(self):
        async def run() -> str:
            with Tapestry() as t:
                router = StepRouter(step="calculate", _config=KnotConfig(id="r"))
    
            auto_param = router.parents["step"]
            result = await auto_param({})
            return result.unwrap()
    
        assert asyncio.run(run()) == "calculate"
