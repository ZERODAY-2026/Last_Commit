from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class AuditLogger:
    """Best-effort writer for the optional Snowflake audit table."""

    def __init__(self, connection: Any | None = None) -> None:
        self.connection = connection

    def log(self, question: str, sql: str | None, query_id: str | None, status: str, runtime_ms: int, retries: int) -> None:
        if self.connection is None or not sql:
            return
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """INSERT INTO DATAMIND_DB.AUDIT.QUERY_LOG
                (EVENT_TS, QUESTION, SQL_TEXT, QUERY_ID, STATUS, RUNTIME_MS, RETRIES)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (datetime.now(timezone.utc), question, sql, query_id, status, runtime_ms, retries),
            )
        finally:
            cursor.close()
