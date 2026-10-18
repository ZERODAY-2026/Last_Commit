from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
import requests

from .models import RouteDecision, SQLProposal
from .schemas import RouterOutput, SqlOutput

load_dotenv()


class GemmaError(RuntimeError):
    """Raised when the local Gemma service cannot produce a valid response."""


class OllamaGemma:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.timeout = timeout

    def _json_prompt(self, prompt: str) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": 512},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        body = response.json()
        try:
            return json.loads(body["response"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise GemmaError("Gemma returned invalid JSON") from exc

    # Maps shortened or alternate values Gemma may return to the exact Literal.
    _INTENT_ALIASES: dict[str, str] = {
        "answer": "answerable",
        "answerable": "answerable",
        "ambiguous": "ambiguous",
        "unsupported": "unsupported",
        "follow_up": "follow_up",
        "followup": "follow_up",
        "follow-up": "follow_up",
        "unanswerable": "unsupported",
        "not_answerable": "unsupported",
    }

    @staticmethod
    def _to_list(value: Any) -> list[str]:
        """Coerce a Gemma field that should be a list but may come back as a
        plain string (e.g. assumptions, tables_used) into a proper list."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Split on semicolons or newlines if the model used those as separators
            for sep in (";", "\n", ","):
                if sep in value:
                    return [item.strip() for item in value.split(sep) if item.strip()]
            return [value.strip()] if value.strip() else []
        return []

    def route(self, question: str, schema: str) -> RouteDecision:
        prompt = (
            "Classify the data question as one of these exact intents: 'answerable', 'ambiguous', 'unsupported', or 'follow_up'.\n"
            "- 'answerable': can be answered from the schema (e.g. counting orders, computing revenue, listing rows)\n"
            "- 'ambiguous': question is unclear and needs clarification\n"
            "- 'unsupported': question asks about data not present in the tables\n"
            "- 'follow_up': question is incomplete and depends on the previous question\n"
            "Return JSON with: intent, reason, clarifying_question.\n"
            f"Schema:\n{schema}\nQuestion: {question}"
        )
        raw = self._json_prompt(prompt)
        raw_intent = str(raw.get("intent", "answerable")).strip().lower()
        if raw_intent in ("ambiguous", "unclear"):
            raw["intent"] = "ambiguous"
        elif raw_intent in ("unsupported", "unanswerable", "not_answerable", "out_of_scope", "impossible"):
            raw["intent"] = "unsupported"
        elif raw_intent in ("follow_up", "followup", "follow-up"):
            raw["intent"] = "follow_up"
        else:
            # Everything else (answer, answerable, count, select, sum, filter, query, etc.) is answerable
            raw["intent"] = "answerable"
        data = RouterOutput.model_validate(raw)
        return RouteDecision(
            status=data.intent,
            reason=data.reason,
            clarification=data.clarifying_question or "",
        )

    def write_sql(self, question: str, schema: str, repair: str | None = None) -> SQLProposal:
        prompt = (
            "Write exactly one Snowflake SELECT statement as JSON with keys sql and "
            "assumptions. Use only the provided tables and columns. Never write, "
            "alter, delete, insert, merge, copy, or use multiple statements. "
            f"\nSchema:\n{schema}\nQuestion: {question}"
        )
        if repair:
            prompt += f"\nPrevious SQL error; repair it: {repair}"
        raw = self._json_prompt(prompt)
        # Gemma sometimes returns assumptions / tables_used as a plain string.
        for field in ("assumptions", "tables_used"):
            if field in raw:
                raw[field] = self._to_list(raw[field])
        data = SqlOutput.model_validate(raw)
        return SQLProposal(sql=data.sql, assumptions=data.assumptions)

    def explain(
        self,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        assumptions: list[str],
    ) -> tuple[str, str]:
        data = self._json_prompt(
            "Explain a database answer using only the supplied rows. Return JSON with "
            "answer and explanation. Do not add facts, numbers, or claims absent from "
            f"the rows. Question: {question}\nSQL: {sql}\nAssumptions: {assumptions}\nRows: {rows}"
        )
        return str(data.get("answer", "")), str(data.get("explanation", ""))
