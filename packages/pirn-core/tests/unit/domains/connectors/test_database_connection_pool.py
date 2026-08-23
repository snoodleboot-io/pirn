"""Tests for :class:`DatabaseConnectionPool`."""

from __future__ import annotations

import unittest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool


class TestDatabaseConnectionPoolInterface(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            await DatabaseConnectionPool().acquire()

    async def test_release_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            await DatabaseConnectionPool().release(None)

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            await DatabaseConnectionPool().close()


class TestDatabaseConnectionPoolHelpers(unittest.TestCase):
    def test_reject_inline_interpolation_braces(self) -> None:
        pool = DatabaseConnectionPool()
        with self.assertRaises(ValueError):
            pool._reject_inline_interpolation("SELECT {col} FROM t")

    def test_reject_inline_interpolation_printf(self) -> None:
        pool = DatabaseConnectionPool()
        with self.assertRaises(ValueError):
            pool._reject_inline_interpolation("SELECT %s FROM t")

    def test_valid_query_passes(self) -> None:
        pool = DatabaseConnectionPool()
        pool._reject_inline_interpolation("SELECT id FROM t WHERE id = ?")

    def test_clear_credentials_nulls_config(self) -> None:
        pool = DatabaseConnectionPool()
        pool._config = "secret"  # type: ignore[attr-defined]
        pool._clear_credentials()
        self.assertIsNone(pool._config)  # type: ignore[attr-defined]


class TestPoolCallConventionConformance(unittest.TestCase):
    """Every shipped pool must be callable through the interface (PIR-833).

    Until PIR-833 the interface took ``execute(query, *args)`` while nine of the
    relational pools took ``execute(query, parameters)`` — so code written
    against :class:`DatabaseConnectionPool` worked on some pools and raised
    ``TypeError`` on others, and every caller in the monorepo was written for
    the majority shape. The rule that would have caught it
    (``reportIncompatibleMethodOverride``) was globally off.

    This test is the runtime half of that repair: it walks every concrete pool
    module and asserts the query methods still accept the interface's own call
    convention, so a new pool cannot quietly reintroduce a private one.
    """

    _QUERY_METHODS = ("execute", "fetch_all", "execute_many")

    @staticmethod
    def _concrete_pools() -> list[type[DatabaseConnectionPool]]:
        import importlib
        import pkgutil

        import pirn.connectors as connectors_pkg

        found: dict[str, type[DatabaseConnectionPool]] = {}
        for module_info in pkgutil.walk_packages(
            connectors_pkg.__path__, prefix="pirn.connectors."
        ):
            if not module_info.name.endswith("_pool"):
                continue
            module = importlib.import_module(module_info.name)
            for name in dir(module):
                candidate = getattr(module, name)
                if (
                    isinstance(candidate, type)
                    and issubclass(candidate, DatabaseConnectionPool)
                    and candidate is not DatabaseConnectionPool
                ):
                    found[f"{candidate.__module__}.{candidate.__name__}"] = candidate
        return list(found.values())

    def test_pools_were_discovered(self) -> None:
        # A discovery bug would make every assertion below vacuously pass.
        self.assertGreater(len(self._concrete_pools()), 10)

    def test_query_methods_keep_the_interface_call_convention(self) -> None:
        import inspect

        for method_name in self._QUERY_METHODS:
            base_params = list(
                inspect.signature(getattr(DatabaseConnectionPool, method_name)).parameters.values()
            )
            for pool_cls in self._concrete_pools():
                method = getattr(pool_cls, method_name, None)
                if method is None or method is getattr(DatabaseConnectionPool, method_name):
                    continue  # inherits the interface's own raise
                params = list(inspect.signature(method).parameters.values())
                with self.subTest(pool=pool_cls.__name__, method=method_name):
                    self.assertEqual(
                        [p.name for p in params],
                        [p.name for p in base_params],
                        f"{pool_cls.__name__}.{method_name} renamed an interface parameter",
                    )
                    self.assertEqual(
                        [p.kind for p in params],
                        [p.kind for p in base_params],
                        f"{pool_cls.__name__}.{method_name} changed a parameter kind",
                    )
