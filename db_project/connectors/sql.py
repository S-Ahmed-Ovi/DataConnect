"""
db_project/connectors/sql.py — dialect-agnostic SQL connector.

One class handles postgres/mysql/mariadb/sqlite/mssql via SQLAlchemy's
create_engine dialect string, instead of a class per DB. Reads (query) and
writes (write_dataframe → used to "convert an upload into a database table")
both go through here.

Drivers are installed separately per dialect (see requirements.txt):
    postgres -> psycopg2-binary
    mysql    -> pymysql
    mssql    -> pyodbc (+ system ODBC driver)
    sqlite   -> built into Python, no driver needed
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import quote_plus

import pandas as pd

_DIALECT_DRIVERS = {
    "postgres":   "postgresql+psycopg2",
    "postgresql": "postgresql+psycopg2",
    "mysql":      "mysql+pymysql",
    "mariadb":    "mysql+pymysql",
    "mssql":      "mssql+pyodbc",
    "sqlite":     "sqlite",
}


class SQLConnector:
    """Tenant/project-agnostic SQL connector. Give it host/port already resolved
    (i.e. if a tunnel was opened, pass the tunneled 127.0.0.1 host/port here)."""

    def __init__(
        self,
        dialect: str,
        host: str = "",
        port: int = 0,
        database: str = "",
        username: str = "",
        password: str = "",
        ssl: bool = True,
        connect_timeout: int = 30,
        extra_params: Optional[dict] = None,
        label: str = "",
    ) -> None:
        self.dialect = dialect.lower()
        if self.dialect not in _DIALECT_DRIVERS:
            raise ValueError(f"Unsupported dialect '{dialect}'. Choose from {sorted(_DIALECT_DRIVERS)}.")
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.ssl = ssl
        self.connect_timeout = connect_timeout
        self.extra_params = extra_params or {}
        self.label = label or f"{dialect}:{database}"
        self._engine = None

    def __enter__(self) -> "SQLConnector":
        self.connect()
        return self

    def __exit__(self, *_exc) -> None:
        self.disconnect()

    # ── connection URL ───────────────────────────────────────────────────

    def _url(self) -> str:
        driver = _DIALECT_DRIVERS[self.dialect]
        if self.dialect == "sqlite":
            # database is a file path here, or ":memory:"
            return "sqlite://" if self.database == ":memory:" else f"sqlite:///{self.database}"
        user = quote_plus(self.username)
        pw = quote_plus(self.password)
        return f"{driver}://{user}:{pw}@{self.host}:{self.port}/{self.database}"

    def connect(self) -> None:
        from sqlalchemy import create_engine, text

        connect_args: dict = {}
        if self.dialect != "sqlite":
            connect_args["connect_timeout"] = self.connect_timeout
            if self.dialect in ("postgres", "postgresql") and self.ssl:
                connect_args["sslmode"] = "require"
            if self.dialect in ("mysql", "mariadb") and self.ssl:
                connect_args["ssl"] = {"ssl_disabled": False}
        connect_args.update(self.extra_params)

        kwargs = dict(connect_args=connect_args, pool_pre_ping=True)
        if self.dialect != "sqlite":
            kwargs.update(pool_size=5, max_overflow=10)

        self._engine = create_engine(self._url(), **kwargs)
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None

    # ── read ─────────────────────────────────────────────────────────────

    def query(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        self._require_connected()
        from sqlalchemy import text
        with self._engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def get_table_names(self) -> list[str]:
        self._require_connected()
        from sqlalchemy import inspect
        return inspect(self._engine).get_table_names()

    # ── write (the "convert upload -> database" step) ──────────────────────

    def write_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        if_exists: str = "replace",     # "replace" | "append" | "fail"
        chunksize: int = 5000,
        dtype: Optional[dict] = None,
    ) -> int:
        """
        Write a DataFrame into `table_name` on this connection.
        Returns number of rows written.
        """
        self._require_connected()
        if if_exists not in ("replace", "append", "fail"):
            raise ValueError("if_exists must be 'replace', 'append', or 'fail'")
        df.to_sql(
            table_name,
            self._engine,
            if_exists=if_exists,
            index=False,
            chunksize=chunksize,
            dtype=dtype,
            method="multi",
        )
        return len(df)

    def _require_connected(self) -> None:
        if self._engine is None:
            raise RuntimeError("Not connected. Use `with SQLConnector(...) as conn:` or call connect().")
