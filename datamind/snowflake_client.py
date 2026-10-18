from __future__ import annotations

import os
import time
from typing import Any

from .models import QueryResult


class SnowflakeQueryError(RuntimeError):
    """Raised when Snowflake cannot execute a validated query."""


class SnowflakeClient:
    def __init__(self, connection: Any | None = None) -> None:
        self.connection = connection
        self.timeout = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))

    def _connect(self) -> Any:
        if self.connection is not None:
            return self.connection
        import snowflake.connector

        self.connection = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "DATAMIND_WH"),
            database=os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_SAMPLE_DATA"),
            schema=os.getenv("SNOWFLAKE_SCHEMA", "TPCH_SF1"),
            role=os.getenv("SNOWFLAKE_ROLE", "DATAMIND_READER"),
        )
        return self.connection

    def execute(self, sql: str, max_rows: int) -> QueryResult:
        started = time.monotonic()
        connection = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {self.timeout}")
            cursor.execute(sql)
            columns = [str(description[0]) for description in cursor.description or []]
            raw_rows = cursor.fetchmany(max_rows + 1)
            truncated = len(raw_rows) > max_rows
            rows = [dict(zip(columns, row)) for row in raw_rows[:max_rows]]
            return QueryResult(
                columns=columns,
                rows=rows,
                query_id=getattr(cursor, "sfqid", None),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                truncated=truncated,
            )
        except Exception as exc:
            raise SnowflakeQueryError(str(exc)) from exc
        finally:
            cursor.close()
