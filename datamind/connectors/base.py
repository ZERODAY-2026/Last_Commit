from __future__ import annotations

from typing import Any, Protocol


class DataConnector(Protocol):
    """Protocol for data execution connectors."""

    def execute(self, sql: str, max_rows: int) -> Any:
        ...


class ModelBackend(Protocol):
    """Protocol for language model backends (Ollama, HuggingFace, etc.)."""

    def generate(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        ...
