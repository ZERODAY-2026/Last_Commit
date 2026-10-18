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

    def route(self, question: str, schema: str) -> RouteDecision:
        data = RouterOutput.model_validate(self._json_prompt(
            "Classify the data question as answerable, ambiguous, unsupported, or "
            "follow_up. Return JSON with intent, reason, clarifying_question. "
            f"Use only this schema:\n{schema}\nQuestion: {question}"
        ))
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
        data = SqlOutput.model_validate(self._json_prompt(prompt))
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
