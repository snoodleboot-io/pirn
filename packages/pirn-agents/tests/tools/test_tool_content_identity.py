"""Content identity for tools (PIR-840).

A tool's content hash decides whether a recorded call can be served on replay.
These tests pin both directions: opted-in tools hash by content (so they replay
across processes), and everything else stays identity-keyed (so replay refuses
rather than substituting a value recorded against a different tool).
"""

from __future__ import annotations

import asyncio
import functools
import sys
import tempfile
import types
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest import mock

from pirn.core.hashing import content_hash
from pydantic import BaseModel

from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.specializations.structured_output._extraction_tool import _ExtractionTool
from pirn_agents.tools.calculator.calculator_tool import CalculatorTool
from pirn_agents.tools.filesystem.read_file_tool import ReadFileTool
from pirn_agents.tools.function_tool import FunctionTool
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_decorator import tool
from pirn_agents.tools.toolset import Toolset
from pirn_agents.tools.web.http_request_tool import HttpRequestTool


class _IdentityOnlyTool(Tool):
    """A tool that does not opt in."""

    @property
    def name(self) -> str:
        return "identity_only"

    @property
    def description(self) -> str:
        return "does not declare content identity"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object"}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return dict(arguments)


class _SameTripleFirstTool(Tool):
    """Opts in with the same triple as :class:`_SameTripleSecondTool`."""

    @property
    def name(self) -> str:
        return "same"

    @property
    def description(self) -> str:
        return "same triple"

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        return {"type": "object"}

    def content_identity(self) -> Mapping[str, Any]:
        return {}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return 1


class _SameTripleSecondTool(_SameTripleFirstTool):
    """Same triple and config, different behaviour; re-declares the opt-in."""

    def content_identity(self) -> Mapping[str, Any]:
        return {}

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return 2


class _UndeclaredTenantTool(_SameTripleFirstTool):
    """Inherits the opt-in without re-declaring it, and adds undeclared config."""

    def __init__(self, *, tenant: str) -> None:
        self._tenant = tenant

    async def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return self._tenant


class _ConstantAuditTool(_IdentityOnlyTool):
    """Overrides the audit form with a constant, as ``ConnectorBase`` does."""

    def _pirn_audit_dict(self) -> Any:
        return {"tool": "constant"}


def _scaled_calculator(factor: int) -> Tool:
    """Build a calculator from a factory-local class."""

    # design-decision-override: a factory-local class is the case under test.
    class Scaled(CalculatorTool):
        async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            output = dict(await super().invoke(arguments))
            output["result"] = output["result"] * factor
            return output

    return Scaled()


def bind_tenant(tenant: str) -> Any:
    """Return a ``functools.wraps`` decorator closing over ``tenant``."""

    # design-decision-override: a closure-capturing decorator is the case under test.
    def decorate(fn: Any) -> Any:
        # design-decision-override: the wrapper's closure is what must not be hashed away.
        @functools.wraps(fn)
        def wrapper(query: str) -> str:
            return fn(query, tenant)

        return wrapper

    return decorate


def tenant_lookup(query: str, tenant: str = "") -> str:
    """Look up a record for a tenant."""
    return f"{tenant}:{query}"


wrapped_lookup = bind_tenant("prod")(tenant_lookup)


def plain_wrapper(query: str) -> str:
    """A wrapper with no closure that still sets ``__wrapped__``."""
    return query


plain_wrapper.__wrapped__ = tenant_lookup  # type: ignore[attr-defined]


def default_tenant(query: str, tenant: str = "prod") -> str:
    """Look up a record for the default tenant."""
    return f"{tenant}:{query}"


def default_object(query: str, sink: object = object()) -> str:
    """A default with no content form."""
    return query


class _CanonicalTenant:
    """Injected state whose author declares what identifies it."""

    def __init__(self, tenant: str) -> None:
        self.tenant = tenant

    def __pirn_canonical__(self) -> dict[str, str]:
        return {"tenant": self.tenant}


class _AddArguments(BaseModel):
    a: int
    b: int


class _Adder:
    def add(self, a: int, b: int) -> int:
        return a + b


def plain_add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def tenant_add(a: int, b: int, state: Any) -> int:
    """Add two integers for a tenant."""
    return a + b


def model_add(arguments: _AddArguments) -> int:
    """Add two integers from a model."""
    return arguments.a + arguments.b


def shadowed(a: int) -> int:
    """First definition, later shadowed."""
    return a


_first_shadowed = shadowed


def shadowed(a: int) -> int:
    """Second definition with the same qualname."""
    return -a


@tool
def decorated_add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def _canonical(value: Any) -> Any:
    return value.__pirn_canonical__()


class TestDefaultIsIdentityKeyed(unittest.TestCase):
    def test_a_tool_that_does_not_opt_in_hashes_differently_per_instance(self) -> None:
        first, second = _IdentityOnlyTool(), _IdentityOnlyTool()

        assert first.content_identity() is None
        assert content_hash(first) != content_hash(second)

    def test_an_identity_keyed_tool_hashes_stably_per_instance(self) -> None:
        tool_instance = _IdentityOnlyTool()

        assert content_hash(tool_instance) == content_hash(tool_instance)

    def test_an_audit_override_cannot_collapse_the_identity_hash(self) -> None:
        """Review of #310: the fallback must not route through a subclass's audit form."""
        first, second = _ConstantAuditTool(), _ConstantAuditTool()

        assert first._pirn_audit_dict() == second._pirn_audit_dict()
        assert content_hash(first) != content_hash(second)

    def test_opting_in_leaves_the_audit_form_identity_keyed(self) -> None:
        first, second = CalculatorTool(), CalculatorTool()

        assert first._pirn_audit_dict() != second._pirn_audit_dict()


class TestOptInIsNotInheritedOrFactoryBuilt(unittest.TestCase):
    def test_a_subclass_that_does_not_redeclare_stays_identity_keyed(self) -> None:
        """Review of #310: an inherited opt-in hid the subclass's extra ``tenant`` argument."""
        prod, test = _UndeclaredTenantTool(tenant="prod"), _UndeclaredTenantTool(tenant="test")

        assert content_hash(prod) != content_hash(test)
        assert content_hash(prod) != content_hash(_UndeclaredTenantTool(tenant="prod"))

    def test_a_subclass_that_redeclares_is_content_identified(self) -> None:
        assert content_hash(_SameTripleSecondTool()) == content_hash(_SameTripleSecondTool())

    def test_classes_defined_in_a_factory_stay_identity_keyed(self) -> None:
        """Review of #310: every factory-built class shares ``<locals>`` in one qualname."""
        ten, thousand = _scaled_calculator(10), _scaled_calculator(1000)

        assert type(ten).__qualname__ == type(thousand).__qualname__
        assert content_hash(ten) != content_hash(thousand)
        assert content_hash(ten) != content_hash(_scaled_calculator(10))


class TestOptedInToolsHashByContent(unittest.TestCase):
    def test_two_calculators_hash_equal(self) -> None:
        assert content_hash(CalculatorTool()) == content_hash(CalculatorTool())

    def test_the_canonical_form_carries_class_triple_and_config(self) -> None:
        canonical = _canonical(CalculatorTool())

        assert canonical["tool"] == "pirn_agents.tools.calculator.calculator_tool.CalculatorTool"
        assert canonical["name"] == "calculator"
        assert canonical["description"] == CalculatorTool().description
        assert canonical["parameters_schema"] == CalculatorTool().parameters_schema
        assert canonical["config"] == {}

    def test_two_classes_with_the_same_triple_hash_differently(self) -> None:
        assert content_hash(_SameTripleFirstTool()) != content_hash(_SameTripleSecondTool())

    def test_description_and_schema_are_part_of_the_hash(self) -> None:
        base = {"name": "extract", "description": "d", "parameters_schema": {"type": "object"}}
        baseline = content_hash(_ExtractionTool(**base))

        assert content_hash(_ExtractionTool(**{**base, "description": "other"})) != baseline
        assert (
            content_hash(_ExtractionTool(**{**base, "parameters_schema": {"type": "array"}}))
            != baseline
        )

    def test_no_opted_in_canonical_form_is_unhashable(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools = [CalculatorTool(), ReadFileTool(root=root), HttpRequestTool(), decorated_add]

            for each in tools:
                assert "unhashable" not in content_hash(each), each


class TestFilesystemRoots(unittest.TestCase):
    def setUp(self) -> None:
        self._first = tempfile.TemporaryDirectory()
        self._second = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._first.cleanup()
        self._second.cleanup()

    def test_the_same_root_spelled_differently_hashes_equal(self) -> None:
        as_string = ReadFileTool(root=self._first.name)
        as_path = ReadFileTool(root=Path(self._first.name) / ".")

        assert content_hash(as_string) == content_hash(as_path)

    def test_a_different_root_hashes_differently(self) -> None:
        assert content_hash(ReadFileTool(root=self._first.name)) != content_hash(
            ReadFileTool(root=self._second.name)
        )


class TestHttpRequestTool(unittest.TestCase):
    def test_the_allow_list_order_does_not_change_the_hash(self) -> None:
        forward = HttpRequestTool(allowed_hosts=("a.example", "b.example"))
        backward = HttpRequestTool(allowed_hosts=("b.example", "a.example"))

        assert content_hash(forward) == content_hash(backward)

    def test_no_allow_list_differs_from_an_empty_allow_list(self) -> None:
        assert content_hash(HttpRequestTool()) != content_hash(HttpRequestTool(allowed_hosts=()))

    def test_an_injected_client_keeps_the_tool_identity_keyed(self) -> None:
        assert HttpRequestTool(client=object()).content_identity() is None

    def test_an_injected_resolver_keeps_the_tool_identity_keyed(self) -> None:
        assert HttpRequestTool(resolver=lambda host: "93.184.216.34").content_identity() is None


class TestFunctionTools(unittest.TestCase):
    def test_a_module_level_function_hashes_equal_across_wrappings(self) -> None:
        first, second = tool(plain_add), tool(plain_add)

        assert first.content_identity() is not None
        assert content_hash(first) == content_hash(second)

    def test_a_decorated_function_resolves_through_its_rebound_name(self) -> None:
        identity = decorated_add.content_identity()

        assert identity is not None
        assert identity["fn"] == f"{__name__}.decorated_add"

    def test_a_closure_stays_identity_keyed(self) -> None:
        # design-decision-override: a nested function is the case under test.
        def closure_add(a: int, b: int) -> int:
            return a + b

        assert tool(closure_add).content_identity() is None

    def test_a_lambda_stays_identity_keyed(self) -> None:
        assert tool(lambda a, b: a + b).content_identity() is None

    def test_a_bound_method_stays_identity_keyed(self) -> None:
        assert tool(_Adder().add).content_identity() is None

    def test_a_partial_stays_identity_keyed(self) -> None:
        wrapped = FunctionTool(
            functools.partial(plain_add, 1),
            name="partial_add",
            description="d",
            parameters_schema={"type": "object"},
            is_async=False,
        )

        assert wrapped.content_identity() is None

    def test_a_shadowed_function_stays_identity_keyed(self) -> None:
        assert tool(_first_shadowed).content_identity() is None
        assert tool(shadowed).content_identity() is not None

    def test_a_stateful_tool_with_plain_state_stays_identity_keyed(self) -> None:
        assert tool(state={"tenant": "prod"})(tenant_add).content_identity() is None

    def test_a_stateful_tool_with_canonical_state_hashes_by_that_state(self) -> None:
        prod = tool(state=_CanonicalTenant("prod"))(tenant_add)
        prod_again = tool(state=_CanonicalTenant("prod"))(tenant_add)
        test = tool(state=_CanonicalTenant("test"))(tenant_add)

        assert content_hash(prod) == content_hash(prod_again)
        assert content_hash(prod) != content_hash(test)

    def test_a_module_level_args_model_is_part_of_the_identity(self) -> None:
        identity = tool(args_model=_AddArguments)(model_add).content_identity()

        assert identity is not None
        assert identity["args_model"] == f"{__name__}._AddArguments"

    def test_a_validator_without_its_model_stays_identity_keyed(self) -> None:
        wrapped = FunctionTool(
            plain_add,
            name="validated_add",
            description="d",
            parameters_schema={"type": "object"},
            is_async=False,
            args_validator=dict,
        )

        assert wrapped.content_identity() is None

    def test_a_custom_validator_beside_a_model_stays_identity_keyed(self) -> None:
        """Review of #310: only the model name was hashed, so the validator was invisible."""
        wrapped = FunctionTool(
            model_add,
            name="model_add",
            description="d",
            parameters_schema={"type": "object"},
            is_async=False,
            args_validator=dict,
            args_model=_AddArguments,
        )

        assert wrapped.content_identity() is None

    def test_a_model_alone_derives_its_validator(self) -> None:
        wrapped = FunctionTool(
            model_add,
            name="model_add",
            description="d",
            parameters_schema={"type": "object"},
            is_async=False,
            args_model=_AddArguments,
        )

        assert asyncio.run(wrapped.invoke({"a": "1", "b": 2})) == 3
        assert wrapped.content_identity() is not None

    def test_a_wraps_decorator_with_a_closure_stays_identity_keyed(self) -> None:
        """Review of #310: ``functools.wraps`` copied the qualname past the closure rule."""
        assert wrapped_lookup.__qualname__ == "tenant_lookup"
        assert tool(wrapped_lookup).content_identity() is None

    def test_any_wrapped_function_stays_identity_keyed(self) -> None:
        assert tool(plain_wrapper).content_identity() is None

    def test_primitive_defaults_are_part_of_the_identity(self) -> None:
        identity = tool(default_tenant).content_identity()

        assert identity is not None
        assert identity["defaults"] == {"positional": ["prod"], "keyword": None}

    def test_a_default_without_a_content_form_stays_identity_keyed(self) -> None:
        assert tool(default_object).content_identity() is None

    def test_a_main_module_function_is_keyed_by_the_script_path(self) -> None:
        """Review of #310: two scripts each defining ``search`` collided as ``__main__.search``."""
        with tempfile.TemporaryDirectory() as directory:
            one, two = Path(directory, "one.py"), Path(directory, "two.py")
            first, second = self._main_identity(one), self._main_identity(two)

        assert first is not None and second is not None
        assert str(one.resolve()) in first["fn"]
        assert first["fn"] != second["fn"]

    def test_a_main_module_without_a_file_stays_identity_keyed(self) -> None:
        """A REPL, notebook, or ``python -c`` has no script path to key by."""
        assert self._main_identity(None) is None

    @staticmethod
    def _main_identity(script: Path | None) -> Mapping[str, Any] | None:
        """Return the identity of a ``search`` tool defined in a stand-in ``__main__``."""
        main = types.ModuleType("__main__")
        if script is not None:
            main.__file__ = str(script)
        search = types.FunctionType(plain_add.__code__, vars(main), "search")
        search.__module__ = "__main__"
        search.__qualname__ = "search"
        vars(main)["search"] = search
        with mock.patch.dict(sys.modules, {"__main__": main}):
            return tool(search).content_identity()


class TestContainersUseEachToolsIdentity(unittest.TestCase):
    def setUp(self) -> None:
        self._first = tempfile.TemporaryDirectory()
        self._second = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._first.cleanup()
        self._second.cleanup()

    def test_toolsets_with_differently_rooted_tools_hash_differently(self) -> None:
        """Regression for the measured false match: both used to hash as ``["read_file"]``."""
        first = Toolset([ReadFileTool(root=self._first.name)])
        second = Toolset([ReadFileTool(root=self._second.name)])

        assert first._pirn_audit_dict() == second._pirn_audit_dict() == ["read_file"]
        assert content_hash(first) != content_hash(second)

    def test_toolsets_of_equal_pure_tools_hash_equal(self) -> None:
        assert content_hash(Toolset([CalculatorTool()])) == content_hash(
            Toolset([CalculatorTool()])
        )

    def test_toolset_order_is_part_of_the_hash(self) -> None:
        calculator = CalculatorTool()
        reader = ReadFileTool(root=self._first.name)

        assert content_hash(Toolset([calculator, reader])) != content_hash(
            Toolset([reader, calculator])
        )

    def test_route_candidates_with_differently_rooted_tools_hash_differently(self) -> None:
        first = RouteCandidate(name="files", tool=ReadFileTool(root=self._first.name))
        second = RouteCandidate(name="files", tool=ReadFileTool(root=self._second.name))

        assert first._pirn_audit_dict() == second._pirn_audit_dict()
        assert content_hash(first) != content_hash(second)

    def test_route_candidates_of_equal_pure_tools_hash_equal(self) -> None:
        first = RouteCandidate(name="math", tool=CalculatorTool(), min_confidence=0.5)
        second = RouteCandidate(name="math", tool=CalculatorTool(), min_confidence=0.5)

        assert content_hash(first) == content_hash(second)

    def test_a_route_candidate_over_an_identity_tool_stays_distinct(self) -> None:
        first = RouteCandidate(name="x", tool=_IdentityOnlyTool())
        second = RouteCandidate(name="x", tool=_IdentityOnlyTool())

        assert content_hash(first) != content_hash(second)
