import unittest
"""Tests for pirn.check — static tapestry validation."""

from pirn.check.validation_issue import ValidationIssue
from pirn.check.validator import validate_tapestry
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry


@knot
async def step_a(x: int) -> int:
    return x + 1


@knot
async def step_b(a: int) -> int:
    return a * 2


@knot
async def step_c(b: int) -> int:
    return b - 1


def build_valid():
    with Tapestry() as t:
        x = Parameter("x", int, _config=KnotConfig(id="x"))
        a = step_a(x=x, _config=KnotConfig(id="a"))
        b = step_b(a=a, _config=KnotConfig(id="b"))
        step_c(b=b, _config=KnotConfig(id="c"))
    return t


def build_empty():
    return Tapestry()



class _StandaloneTests(unittest.TestCase):
    def test_valid_tapestry_passes(self):
        result = validate_tapestry(build_valid())
        assert result.ok
        assert not result.errors
    
    
    def test_empty_tapestry_warns(self):
        result = validate_tapestry(build_empty())
        assert result.warnings
        assert any("no knots" in i.message for i in result.warnings)
    
    
    def test_ok_property_false_when_errors(self):
        result = validate_tapestry(build_empty())
        # empty tapestry only produces a warning, not an error
        assert result.ok  # warnings don't block ok
    
        issue = ValidationIssue("error", "x", "something bad")
        result.issues.append(issue)
        assert not result.ok
    
    
    def test_no_false_positives_on_linear_chain(self):
        result = validate_tapestry(build_valid())
        assert not result.issues or all(i.severity == "warning" for i in result.issues)
    
    
    def test_validation_issue_str_with_knot_id(self):
        issue = ValidationIssue("error", "my_knot", "something bad")
        assert "ERROR" in str(issue)
        assert "[my_knot]" in str(issue)
        assert "something bad" in str(issue)
    
    
    def test_validation_issue_str_without_knot_id(self):
        issue = ValidationIssue("warning", None, "generic warning")
        assert "WARNING" in str(issue)
        assert "[" not in str(issue)
