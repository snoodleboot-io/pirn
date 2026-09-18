"""Pools whose store has no multi-statement transaction refuse to fake one (PIR-873).

``DatabaseConnectionPool.transaction()``'s contract says a pool whose store offers
no multi-statement transaction through the surface it drives must raise
``NotImplementedError`` naming that store, rather than yield a scope that would
not be atomic. This pins that for every such pool: the refusal is explicit, it
names the store, and — crucially — it happens *before* any statement runs, so a
caller who wrongly believed the block was atomic cannot have written half of it.

On the pre-PIR-873 tree every one of these pools inherited the base's
``"<Pool> must implement transaction()"`` — a message that reads as a gap to be
filled rather than a decision, which is exactly how a later reader ends up
implementing a non-atomic scope for a store that cannot honour one.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.bigquery_pool import BigqueryPool
from pirn.connectors.databases.clickhouse_pool import ClickhousePool
from pirn.connectors.databases.databricks_pool import DatabricksPool
from pirn.connectors.databases.dremio_pool import DremioPool
from pirn.connectors.document.arangodb_pool import ArangoDBPool
from pirn.connectors.document.cosmosdb_pool import CosmosDBPool
from pirn.connectors.document.couchbase_pool import CouchbasePool
from pirn.connectors.document.couchdb_pool import CouchDBPool
from pirn.connectors.document.firestore_pool import FirestorePool
from pirn.connectors.graph.memgraph_pool import MemgraphPool
from pirn.connectors.graph.orientdb_pool import OrientDBPool
from pirn.connectors.timeseries.influxdb_pool import InfluxDBPool
from pirn.connectors.timeseries.kdb_pool import KdbPool
from pirn.connectors.timeseries.questdb_pool import QuestDBPool
from pirn.connectors.timeseries.victoriametrics_pool import VictoriaMetricsPool

# pool class -> the keyword its injection seam uses, and the store it must name.
REFUSING_POOLS: list[tuple[type[DatabaseConnectionPool], str, str]] = [
    (BigqueryPool, "client", "BigQuery"),
    (ClickhousePool, "client", "ClickHouse"),
    (DatabricksPool, "client", "Databricks SQL"),
    (DremioPool, "connection", "Dremio"),
    (QuestDBPool, "pool", "QuestDB"),
    (InfluxDBPool, "client", "InfluxDB"),
    (KdbPool, "connection", "kdb+"),
    (VictoriaMetricsPool, "client", "VictoriaMetrics"),
    (ArangoDBPool, "db", "ArangoDB"),
    (CosmosDBPool, "container_client", "Cosmos DB"),
    (CouchbasePool, "cluster", "Couchbase"),
    (CouchDBPool, "session", "CouchDB"),
    (FirestorePool, "client", "Firestore"),
    (MemgraphPool, "connection", "Memgraph"),
    (OrientDBPool, "client", "OrientDB"),
]


def _build(pool_class: type[DatabaseConnectionPool], keyword: str) -> DatabaseConnectionPool:
    """Construct the pool through its injection seam, with a stand-in that records use."""
    return pool_class(**{keyword: object()})


@pytest.mark.parametrize(
    ("pool_class", "keyword", "store"), REFUSING_POOLS, ids=lambda v: getattr(v, "__name__", v)
)
def test_transaction_refuses_and_names_the_store(
    pool_class: type[DatabaseConnectionPool], keyword: str, store: str
) -> None:
    pool = _build(pool_class, keyword)
    with pytest.raises(NotImplementedError) as raised:
        pool.transaction()
    message = str(raised.value)
    assert pool_class.__name__ in message
    assert store in message
    assert "no multi-statement transaction" in message
    # Not the base class's "fill this in" message.
    assert "must implement transaction()" not in message


@pytest.mark.parametrize(
    ("pool_class", "keyword", "store"), REFUSING_POOLS, ids=lambda v: getattr(v, "__name__", v)
)
def test_refusal_touches_no_driver(
    pool_class: type[DatabaseConnectionPool], keyword: str, store: str
) -> None:
    """The refusal happens before the driver is touched, so nothing is half-written."""

    class _Tripwire:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"{pool_class.__name__}.transaction() touched driver.{name}")

    pool = pool_class(**{keyword: _Tripwire()})
    with pytest.raises(NotImplementedError):
        pool.transaction()


def test_every_pool_in_the_package_answers_transaction() -> None:
    """No pool is left inheriting the base's unimplemented ``transaction()``.

    A pool that neither implements an atomic scope nor refuses one is the defect:
    a caller gets ``NotImplementedError("... must implement transaction()")`` at
    run time, mid-pipeline, with no statement of whether atomicity is possible.
    """
    import importlib
    import pkgutil

    from pirn import connectors
    from pirn.connectors.database_transaction import DatabaseTransaction

    unanswered: list[str] = []
    prefix = connectors.__name__ + "."
    for _, module_name, _ in pkgutil.walk_packages(connectors.__path__, prefix):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for obj in vars(module).values():
            if not (isinstance(obj, type) and obj.__module__ == module_name):
                continue
            if not issubclass(obj, DatabaseConnectionPool):
                continue
            if obj is DatabaseConnectionPool or issubclass(obj, DatabaseTransaction):
                # A transaction handle answers `transaction()` through
                # DatabaseTransaction, which refuses to nest one.
                continue
            if "transaction" not in obj.__dict__:
                unanswered.append(f"{obj.__module__}.{obj.__qualname__}")
    assert unanswered == []
