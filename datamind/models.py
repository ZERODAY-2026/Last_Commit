from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class RouteDecision:
    status: Literal["answerable", "ambiguous", "unsupported", "follow_up"]
    reason: str = ""
    clarification: str = ""
    assumptions: list[str] = field(default_factory=list)


@dataclass
class SQLProposal:
    sql: str
    assumptions: list[str] = field(default_factory=list)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    query_id: str | None
    elapsed_ms: int
    truncated: bool = False


@dataclass
class Evidence:
    question: str
    answer: str
    explanation: str
    sql: str | None
    assumptions: list[str]
    columns: list[str]
    rows: list[dict[str, Any]]
    query_id: str | None
    elapsed_ms: int
    status: str = "success"
    warning: str | None = None

    def to_contract(self):
        from .schemas import Evidence as EvidenceContract

        warnings = [self.warning] if self.warning else []
        return EvidenceContract(
            question=self.question,
            sql=self.sql,
            snowflake_query_id=self.query_id,
            rows=self.rows,
            row_count=len(self.rows),
            truncated="truncated" in warnings,
            runtime_ms=self.elapsed_ms,
            assumptions=self.assumptions,
            warnings=warnings,
        )
