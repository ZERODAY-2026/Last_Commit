from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationTurn:
    turn_id: int
    question: str
    sql: str | None = None
    summary: str = ""
    rows_count: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)


@dataclass
class ConversationState:
    """Tracks conversation history with questions, executed SQL, and result summaries."""

    turns: list[ConversationTurn] = field(default_factory=list)

    def add_turn(
        self,
        question: str,
        sql: str | None = None,
        summary: str = "",
        rows_count: int = 0,
        rows: list[dict[str, Any]] | None = None,
        columns: list[str] | None = None,
    ) -> ConversationTurn:
        turn = ConversationTurn(
            turn_id=len(self.turns) + 1,
            question=question,
            sql=sql,
            summary=summary,
            rows_count=rows_count,
            rows=rows or [],
            columns=columns or [],
        )
        self.turns.append(turn)
        return turn

    @property
    def last_turn(self) -> ConversationTurn | None:
        return self.turns[-1] if self.turns else None

    def context_prompt(self, max_turns: int = 3) -> str:
        if not self.turns:
            return ""
        recent = self.turns[-max_turns:]
        lines = ["Recent conversation context:"]
        for t in recent:
            lines.append(f"- Turn {t.turn_id}: Question: '{t.question}'")
            if t.sql:
                lines.append(f"  Executed SQL: {t.sql}")
            if t.rows:
                row_strs = []
                for r in t.rows[:5]:
                    row_strs.append(", ".join(f"{k}: {v}" for k, v in r.items()))
                lines.append(f"  Result Rows:\n    " + "\n    ".join(row_strs))
            elif t.summary:
                lines.append(f"  Summary: {t.summary}")
        return "\n".join(lines)

    @staticmethod
    def sql_diff(prev_sql: str | None, current_sql: str | None) -> str:
        """Compute visual diff between previous SQL and modified follow-up SQL."""
        if not prev_sql or not current_sql or prev_sql == current_sql:
            return ""
        diff = difflib.unified_diff(
            prev_sql.splitlines(),
            current_sql.splitlines(),
            fromfile="Previous SQL",
            tofile="Follow-up SQL",
            lineterm="",
        )
        return "\n".join(diff)

    def clear(self) -> None:
        self.turns.clear()
