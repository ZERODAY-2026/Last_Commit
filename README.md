# PS-1 DataMind: Talk to Your Data

## Problem Statement
Organizations hold large amounts of information in databases, spreadsheets, documents and other sources. Getting a useful answer often takes technical skills, specialised queries or hours of manual searching, so the people who understand the questions best are often the least able to reach the data.

The challenge: Create an AI-powered data experience that lets people ask questions in everyday language and get useful answers grounded in the available data, with enough explanation that users trust the response reflects the information actually examined.

Our approach: DataMind uses Gemma 3 4B through local Ollama inference to generate SQL, validates the generated SQL with SQLGlot, and executes approved queries against Snowflake. Answers are constructed from the actual returned rows, with the SQL and Snowflake query ID available for verification.

# DataMind: Talk to Your Data

DataMind is a text-to-SQL agent for Snowflake. A local Gemma model classifies
questions, writes read-only Snowflake SQL, and explains returned rows. The
application never treats model output as the answer: Snowflake is queried at
question time and the UI exposes the SQL, rows, query ID, assumptions, and
runtime as evidence.

## Quick start

1. Install Python 3.11+, Ollama, and a local Gemma model:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ollama pull gemma3:4b
   ```

2. Copy `.env.example` to `.env` and export its values. Configure a
   Snowflake read-only role and credentials; do not commit them.
3. Start the UI:

   ```bash
   streamlit run app/streamlit_app.py
   ```

   Or use the CLI:

   ```bash
   python -m datamind.cli "Which region had the highest revenue?"
   ```

4. Run checks:

   ```bash
   pytest
   pytest tests/test_validator.py
   ruff check .
   ```

For Snowflake setup, an administrator can review and run
`scripts/setup_snowflake.sql`. The app itself should use the
`DATAMIND_READER` role only.

## Architecture

`question -> local Gemma router -> local Gemma SQL writer -> sqlglot validator
-> Snowflake -> local Gemma explainer -> number/evidence checks -> UI`.

The model has no database connection. The Snowflake adapter is the only
component that executes SQL, and the validator permits one read-only query
against tables listed in the selected YAML config. See
`docs/architecture.md`, `docs/design_language.md`, and
`DataMind_Project_Plan.md`.

## Dataset switching

Dataset-specific metadata lives in `configs/*.yaml`. Set
`DATASET_CONFIG=configs/tpch.yaml` or add another config with database, schema, tables,
joins, synonyms, and row limits. The same orchestrator should work without
dataset-specific Python code.

## Scope and limitations

This first implementation requires a live Snowflake account and local Ollama
for the end-to-end demo. A second-dataset config template and golden-question
starter set are included, but a licensed second dataset still needs to be
loaded and evaluated before judging.
