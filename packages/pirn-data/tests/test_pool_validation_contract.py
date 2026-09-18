"""Every pool-backed knot in ``pirn-data`` rejects a non-pool the same way (PIR-873).

The audit found 72 hand-written ``isinstance(x, DatabaseConnectionPool)`` guards
across 46 modules. Each was free to word its message differently, to check only
some of its pool arguments, or to omit the check — and some did. This test walks
the package, finds every knot whose ``process()`` takes a pool-shaped argument,
calls ``process()`` with a non-pool in that position, and asserts the one message
:class:`~pirn_data.pool_validator.PoolValidator` produces.

It fails on the pre-PIR-873 tree: ``SqlSource`` said "must be a
DatabaseConnectionPool instance", so the message was not shared.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import pkgutil
import re
from typing import Any

import pytest
from pirn.core.knot import Knot

import pirn_data
from pirn_data.pool_validator import PoolValidator


def _pool_backed_knots() -> list[tuple[type[Knot], tuple[str, ...]]]:
    """Every ``Knot`` in ``pirn_data`` whose ``process()`` takes pool arguments."""
    found: dict[str, tuple[type[Knot], tuple[str, ...]]] = {}
    prefix = pirn_data.__name__ + "."
    for _, module_name, _ in pkgutil.walk_packages(pirn_data.__path__, prefix):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for obj in vars(module).values():
            if not (isinstance(obj, type) and obj.__module__ == module_name):
                continue
            if not (issubclass(obj, Knot) and obj is not Knot):
                continue
            try:
                signature = inspect.signature(obj.process)
            except (TypeError, ValueError):
                continue
            pools = tuple(
                name for name in signature.parameters if name == "pool" or name.endswith("_pool")
            )
            if pools:
                found[f"{obj.__module__}.{obj.__qualname__}"] = (obj, pools)
    return [found[key] for key in sorted(found)]


_KNOTS = _pool_backed_knots()


def test_the_walk_found_the_pool_backed_knots() -> None:
    assert len(_KNOTS) >= 40, [knot.__name__ for knot, _ in _KNOTS]


@pytest.mark.parametrize(
    ("knot_class", "pool_names"),
    _KNOTS,
    ids=[knot.__name__ for knot, _ in _KNOTS],
)
def test_first_pool_argument_is_rejected_with_the_shared_message(
    knot_class: type[Knot], pool_names: tuple[str, ...]
) -> None:
    signature = inspect.signature(knot_class.process)
    kwargs: dict[str, Any] = {
        name: parameter.default if parameter.default is not parameter.empty else None
        for name, parameter in signature.parameters.items()
        if name not in ("self",) and parameter.kind is not parameter.VAR_KEYWORD
    }
    kwargs[pool_names[0]] = "not-a-pool"
    expected = f"{knot_class.__name__}: {pool_names[0]} must be a DatabaseConnectionPool"
    with pytest.raises(TypeError, match=re.escape(expected) + r"\Z"):
        asyncio.run(knot_class.process(knot_class.__new__(knot_class), **kwargs))


def test_validator_checks_arguments_in_the_order_given() -> None:
    with pytest.raises(TypeError, match="target_pool must be a DatabaseConnectionPool"):
        PoolValidator.validate_pools("Example", target_pool="nope", source_pool="also-nope")


def test_optional_pool_accepts_none_but_not_a_non_pool() -> None:
    PoolValidator.validate_optional_pools("Example", dim_pool=None)
    with pytest.raises(TypeError, match="Example: dim_pool must be a DatabaseConnectionPool"):
        PoolValidator.validate_optional_pools("Example", dim_pool=object())
