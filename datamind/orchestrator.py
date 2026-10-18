from __future__ import annotations

from .config import DatasetConfig
from .gemma_client import GemmaError, OllamaGemma
from .models import Evidence
from .number_check import answer_numbers_are_grounded
from .snowflake_client import SnowflakeClient, SnowflakeQueryError
from .validator import ValidationError, validate_sql


def _format_history(history: Any) -> str:
    if not history:
        return ""
    if hasattr(history, "context_prompt"):
        return history.context_prompt(max_turns=3)
    if isinstance(history, list):
        lines = ["Previous conversation context:"]
        for idx, item in enumerate(history[-3:], start=1):
            if isinstance(item, dict):
                if "evidence" in item:
                    ev = item["evidence"]
                    q = item.get("question", getattr(ev, "question", ""))
                    sql = getattr(ev, "sql", None)
                    rows = getattr(ev, "rows", [])
                    ans = getattr(ev, "answer", "")
                    lines.append(f"Turn {idx}:")
                    lines.append(f"  User Question: {q}")
                    if sql:
                        lines.append(f"  Executed SQL: {sql}")
                    if rows:
                        row_strs = [", ".join(f"{k}: {v}" for k, v in r.items()) for r in rows[:5]]
                        lines.append("  Result Rows:\n    " + "\n    ".join(row_strs))
                    if ans:
                        lines.append(f"  Answer: {ans}")
                elif "sql" in item or "rows" in item:
                    q = item.get("question", "")
                    sql = item.get("sql")
                    rows = item.get("rows", [])
                    ans = item.get("answer", "")
                    lines.append(f"Turn {idx}:")
                    lines.append(f"  User Question: {q}")
                    if sql:
                        lines.append(f"  Executed SQL: {sql}")
                    if rows:
                        row_strs = [", ".join(f"{k}: {v}" for k, v in r.items()) for r in rows[:5]]
                        lines.append("  Result Rows:\n    " + "\n    ".join(row_strs))
                    if ans:
                        lines.append(f"  Answer: {ans}")
                elif "role" in item and "content" in item:
                    lines.append(f"{item['role']}: {item['content']}")
        return "\n".join(lines)
    return str(history)


class DataMind:
    def __init__(self, config: DatasetConfig, gemma: OllamaGemma, snowflake: SnowflakeClient, audit=None) -> None:
        self.config = config
        self.gemma = gemma
        self.snowflake = snowflake
        self.audit = audit

    def answer(self, question: str, history: Any = None) -> Evidence:
        history_text = _format_history(history)
        if history_text:
            routing_question = (
                f"{history_text}\n\n"
                f"Current Question: {question}\n\n"
                f"Instruction: If the current question references entities, metrics, or filters from the previous conversation (e.g. 'these same countries', 'them', 'for those', 'what about 2010'), classify as 'follow_up' or 'answerable', NOT 'ambiguous'."
            )
            sql_question = (
                f"{history_text}\n\n"
                f"Current Question: {question}\n\n"
                f"Instruction: Answer the Current Question. If this is a follow-up question referencing entities from the previous question/results (e.g. 'these same countries', 'them', 'for those'), resolve them using the entities from the previous conversation (either by listing the ENTITY names in an IN clause or using a Common Table Expression / subquery). Ignore any language instructions like 'in hindi' when writing the SQL query."
            )
        else:
            routing_question = question
            sql_question = question

        route = self.gemma.route(routing_question, self.config.prompt_schema())
        if route.status not in ("answerable", "follow_up"):
            message = route.clarification or route.reason or "This question is outside the configured dataset."
            examples = [item["q"] for item in self.config.examples] if self.config.examples else []
            suggestions = self.gemma.suggest_questions(question, self.config.prompt_schema(), examples)
            return Evidence(
                question=question,
                answer=message,
                explanation=route.reason,
                sql=None,
                assumptions=route.assumptions,
                columns=[],
                rows=[],
                query_id=None,
                elapsed_ms=0,
                status=route.status,
                suggested_questions=suggestions,
            )

        proposal = self.gemma.write_sql(sql_question, self.config.prompt_schema())
        last_error = None
        retries = 0
        for attempt in range(3):
            try:
                validated = validate_sql(
                    proposal.sql,
                    self.config.qualified_tables,
                    self.config.max_rows,
                    self.config.blocked_columns,
                )
                result = self.snowflake.execute(validated.sql, self.config.max_rows)
                break
            except (ValidationError, GemmaError, SnowflakeQueryError) as exc:
                last_error = str(exc)
                if attempt == 2:
                    examples = [item["q"] for item in self.config.examples] if self.config.examples else []
                    suggestions = self.gemma.suggest_questions(question, self.config.prompt_schema(), examples)
                    evidence = Evidence(
                        question,
                        "I could not safely answer this question.",
                        last_error,
                        proposal.sql,
                        proposal.assumptions,
                        [],
                        [],
                        None,
                        0,
                        "error",
                        suggested_questions=suggestions,
                    )
                    if self.audit:
                        self.audit.log(question, proposal.sql, None, "error", 0, retries)
                    return evidence
                retries += 1
                proposal = self.gemma.write_sql(sql_question, self.config.prompt_schema(), repair=last_error)
        if not result.rows:
            examples = [item["q"] for item in self.config.examples] if self.config.examples else []
            suggestions = self.gemma.suggest_questions(question, self.config.prompt_schema(), examples)
            return Evidence(
                question,
                "No rows matched the question.",
                "The query ran successfully but returned no rows.",
                validated.sql,
                proposal.assumptions,
                result.columns,
                [],
                result.query_id,
                result.elapsed_ms,
                warning="empty_result",
                suggested_questions=suggestions,
            )
        answer, explanation = self.gemma.explain(question, validated.sql, result.rows, proposal.assumptions)
        warning = None
        if not answer_numbers_are_grounded(answer, result.rows, question):
            warning = "The explanation contained a number not present in the result rows; review the evidence before relying on it."
        if result.truncated:
            warning = (warning + " " if warning else "") + "Results were truncated at the configured row limit."
        evidence = Evidence(question, answer, explanation, validated.sql, proposal.assumptions, result.columns, result.rows, result.query_id, result.elapsed_ms, warning=warning)
        if self.audit:
            self.audit.log(question, validated.sql, result.query_id, "success", result.elapsed_ms, retries)
        return evidence
