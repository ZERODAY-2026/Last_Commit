from __future__ import annotations

from .config import DatasetConfig
from .gemma_client import GemmaError, OllamaGemma
from .models import Evidence
from .number_check import answer_numbers_are_grounded
from .snowflake_client import SnowflakeClient, SnowflakeQueryError
from .validator import ValidationError, validate_sql


class DataMind:
    def __init__(self, config: DatasetConfig, gemma: OllamaGemma, snowflake: SnowflakeClient, audit=None) -> None:
        self.config = config
        self.gemma = gemma
        self.snowflake = snowflake
        self.audit = audit

    def answer(self, question: str, history: list[dict[str, str]] | None = None) -> Evidence:
        if history:
            history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history[-4:])
            routing_question = f"{question}\n\nRecent conversation:\n{history_text}"
            sql_question = (
                f"Previous conversation:\n{history_text}\n\n"
                f"Focus strictly on answering the CURRENT QUESTION below. If the current question is a new question, ignore the previous conversation.\n"
                f"Current Question: {question}"
            )
        else:
            routing_question = question
            sql_question = question

        route = self.gemma.route(routing_question, self.config.prompt_schema())
        if route.status not in ("answerable", "follow_up"):
            message = route.clarification or route.reason or "This question is outside the configured dataset."
            return Evidence(question, message, route.reason, None, route.assumptions, [], [], None, 0, route.status)

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
                    evidence = Evidence(question, "I could not safely answer this question.", last_error, proposal.sql, proposal.assumptions, [], [], None, 0, "error")
                    if self.audit:
                        self.audit.log(question, proposal.sql, None, "error", 0, retries)
                    return evidence
                retries += 1
                proposal = self.gemma.write_sql(sql_question, self.config.prompt_schema(), repair=last_error)
        if not result.rows:
            return Evidence(question, "No rows matched the question.", "The query ran successfully but returned no rows.", validated.sql, proposal.assumptions, result.columns, [], result.query_id, result.elapsed_ms, warning="empty_result")
        answer, explanation = self.gemma.explain(question, validated.sql, result.rows, proposal.assumptions)
        warning = None
        if not answer_numbers_are_grounded(answer, result.rows):
            warning = "The explanation contained a number not present in the result rows; review the evidence before relying on it."
        if result.truncated:
            warning = (warning + " " if warning else "") + "Results were truncated at the configured row limit."
        evidence = Evidence(question, answer, explanation, validated.sql, proposal.assumptions, result.columns, result.rows, result.query_id, result.elapsed_ms, warning=warning)
        if self.audit:
            self.audit.log(question, validated.sql, result.query_id, "success", result.elapsed_ms, retries)
        return evidence
