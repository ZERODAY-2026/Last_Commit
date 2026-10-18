from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


class ValidationError(ValueError):
    """Raised for SQL that is unsafe or outside the configured dataset."""


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str


def validate_sql(
    sql: str,
    allowed_tables: set[str],
    max_rows: int,
    blocked_columns: set[str] | None = None,
) -> ValidatedSQL:
    candidate = sql.strip()
    if not candidate:
        raise ValidationError("Gemma returned an empty SQL statement")
    if "--" in candidate or "/*" in candidate or "*/" in candidate:
        raise ValidationError("SQL comments are not allowed")
    try:
        statements = sqlglot.parse(candidate, read="snowflake")
    except sqlglot.errors.ParseError as exc:
        raise ValidationError(f"SQL could not be parsed: {exc}") from exc
    if len(statements) != 1:
        raise ValidationError("Only one SQL statement is allowed")
    statement = statements[0]
    if not isinstance(statement, exp.Select):
        raise ValidationError("Only SELECT queries are allowed")
    if any(isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Command)) for node in statement.walk()):
        raise ValidationError("Write and command statements are not allowed")

    tables = set()
    for table in statement.find_all(exp.Table):
        name = ".".join(part for part in (table.catalog, table.db, table.name) if part)
        tables.add(name.upper())
    normalized_allowed = {table.upper() for table in allowed_tables}
    for table in tables:
        if table not in normalized_allowed and table.split(".")[-1] not in {value.split(".")[-1] for value in normalized_allowed}:
            raise ValidationError(f"Table is not allowed: {table}")
    blocked = {column.upper() for column in (blocked_columns or set())}
    for column in statement.find_all(exp.Column):
        if column.name.upper() in blocked:
            raise ValidationError(f"Column is blocked: {column.name}")

    if not statement.args.get("limit"):
        statement = statement.limit(max_rows)
    return ValidatedSQL(sql=statement.sql(dialect="snowflake"))
