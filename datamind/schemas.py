from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RouterOutput(BaseModel):
    intent: Literal["answerable", "ambiguous", "unsupported", "follow_up"]
    clarifying_question: Optional[str] = None
    reason: str = ""


class SqlOutput(BaseModel):
    sql: str
    assumptions: List[str] = Field(default_factory=list)
    tables_used: List[str] = Field(default_factory=list)


class Evidence(BaseModel):
    question: str
    sql: Optional[str] = None
    snowflake_query_id: Optional[str] = None
    rows: List[Dict] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    runtime_ms: int = 0
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class Answer(BaseModel):
    summary: str
    how_obtained: str = ""
    evidence: Evidence
    numbers_verified: bool = False
