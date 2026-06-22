"""Shared fixtures for Spark Tier-3 unit tests.

A SparkSession is heavy to boot, so we start one once per pytest session
via a session-scoped autouse fixture and tear it down at the end. Tests
acquire the active session through ``pyspark.sql.SparkSession.getActiveSession()``
or by depending on the ``_spark_session`` fixture explicitly.

PySpark version constraint: ``pyspark>=4.0`` for Python 3.13+.
"""

from __future__ import annotations

import pytest

pyspark = pytest.importorskip("pyspark")
pytest.importorskip("pyspark.sql")


@pytest.fixture(scope="session", autouse=True)
def _spark_session():
    """Start a single local SparkSession once per test session."""
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.master("local[1]")
        .appName("pirn-test")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.warehouse.dir", "/tmp/pirn-spark-warehouse")
        .getOrCreate()
    )
    yield session
    session.stop()
