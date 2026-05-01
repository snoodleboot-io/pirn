"""Configuration dataclass for :class:`MssqlPool`."""

from __future__ import annotations

from typing import ClassVar

from pirn.domains.connectors.connection_config import ConnectionConfig
from pirn.domains.connectors.connection_config_decorator import connection_config


@connection_config(frozen=True)
class MssqlConfig(ConnectionConfig):
    """Configuration for an aioodbc-based MSSQL connection pool.

    Provide ``dsn`` (a full ODBC connection string, preferred) OR the
    discrete fields ``host``/``port``/``user``/``password``/``database``
    plus ``driver``. ``dsn`` wins when both are given.
    """

    dsn: str | None = None
    host: str | None = None
    port: int = 1433
    user: str | None = None
    password: str | None = None
    database: str | None = None
    driver: str = "ODBC Driver 18 for SQL Server"
    min_size: int = 1
    max_size: int = 10
    autocommit: bool = True

    sensitive_fields: ClassVar[tuple[str, ...]] = ()

    def build_dsn(self) -> str:
        """Return the effective ODBC connection string.

        Returns ``dsn`` verbatim when provided; otherwise constructs a
        standard DSN from the discrete fields.
        """
        if self.dsn:
            return self.dsn
        parts = [f"DRIVER={{{self.driver}}}"]
        if self.host is not None:
            server = self.host if self.port is None else f"{self.host},{self.port}"
            parts.append(f"SERVER={server}")
        if self.database is not None:
            parts.append(f"DATABASE={self.database}")
        if self.user is not None:
            parts.append(f"UID={self.user}")
        if self.password is not None:
            parts.append(f"PWD={self.password}")
        return ";".join(parts) + ";"
