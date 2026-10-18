# Architecture

DataMind keeps reasoning and execution separate. Gemma receives the question
and a compact YAML-derived schema. It returns a route decision or a proposed
SQL statement. `sqlglot` parses the statement and enforces one read-only query,
an allowlist of configured tables, and a maximum row limit. Only validated SQL
reaches Snowflake.

Snowflake result rows are passed back to Gemma with the original question and
SQL. The explainer is instructed not to add facts outside those rows. The
result is returned as an evidence object containing answer, explanation, SQL,
assumptions, rows, query ID, elapsed time, and warnings. The UI renders that
object directly.

Local Ollama is the default Gemma runtime. Model acquisition is a setup-time
operation; the runtime does not use Snowflake Cortex or a hosted LLM API.
