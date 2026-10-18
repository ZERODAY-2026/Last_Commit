from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DatasetConfig:
    display_name: str
    name: str
    description: str
    database: str
    schema: str
    tables: dict[str, Any]
    joins: list[str]
    synonyms: dict[str, Any]
    metrics: dict[str, str]
    examples: list[dict[str, str]]
    blocked_columns: set[str]
    max_rows: int

    @classmethod
    def from_file(cls, path: str | Path) -> "DatasetConfig":
        raw = yaml.safe_load(Path(path).read_text()) or {}
        snowflake = raw.get("snowflake", {})
        limits = raw.get("limits", raw.get("guardrails", {}))
        guardrails = raw.get("guardrails", {})
        return cls(
            name=raw["dataset"],
            display_name=raw.get("display_name", raw["dataset"]),
            description=raw.get("description", ""),
            database=snowflake["database"],
            schema=snowflake["schema"],
            tables=raw.get("tables", {}),
            joins=raw.get("joins", []),
            synonyms=raw.get("synonyms", {}),
            metrics=raw.get("metrics", {}),
            examples=raw.get("examples", []),
            blocked_columns={str(column).upper() for column in guardrails.get("blocked_columns", [])},
            max_rows=int(limits.get("max_rows", 1000)),
        )

    def prompt_schema(self) -> str:
        lines = [f"Dataset: {self.name} - {self.description}", "Tables:"]
        for table, details in self.tables.items():
            lines.append(f"- {table}: {details.get('description', '')}")
            for column, metadata in details.get("columns", {}).items():
                lines.append(
                    f"  - {column} ({metadata.get('type', 'UNKNOWN')}): "
                    f"{metadata.get('description', '')}"
                )
        if self.joins:
            lines.append("Allowed joins:")
            lines.extend(f"- {join}" for join in self.joins)
        if self.synonyms:
            lines.append("Business synonyms:")
            lines.extend(f"- {key}: {', '.join(value) if isinstance(value, list) else value}" for key, value in self.synonyms.items())
        if self.metrics:
            lines.append("Business metrics:")
            lines.extend(f"- {key}: {value}" for key, value in self.metrics.items())
        if self.examples:
            lines.append("Examples:")
            lines.extend(f"- Question: {example['q']}\n  SQL: {example['sql']}" for example in self.examples)
        return "\n".join(lines)

    @property
    def qualified_tables(self) -> set[str]:
        return {f"{self.database}.{self.schema}.{table}".upper() for table in self.tables}
