from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    id: str
    purpose: str
    sql: str
    depends_on: List[str] = Field(default_factory=list)


class MultiStepPlan(BaseModel):
    complexity: str = "multi_step"
    steps: List[PlanStep] = Field(default_factory=list)


def format_steps_as_cte(plan: MultiStepPlan) -> str:
    """Combine multi-step plan into a single robust Snowflake CTE query."""
    if not plan.steps:
        return ""
    if len(plan.steps) == 1:
        return plan.steps[0].sql.strip()

    cte_parts = []
    final_sql = ""
    for i, step in enumerate(plan.steps):
        sql = step.sql.strip().rstrip(";")
        # Remove any leading WITH
        if sql.upper().startswith("WITH "):
            sql = sql[5:].strip()
        if i == len(plan.steps) - 1:
            final_sql = sql
        else:
            cte_parts.append(f"{step.id} AS (\n  {sql}\n)")

    if cte_parts and final_sql:
        return f"WITH {', '.join(cte_parts)}\n{final_sql}"
    return final_sql or plan.steps[0].sql
