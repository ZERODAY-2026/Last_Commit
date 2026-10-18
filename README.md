# PS-1 DataMind: Talk to Your Data

## Problem Statement
Organizations hold large amounts of information in databases, spreadsheets, documents, and other sources. Getting a useful answer often takes technical skills, specialized queries, or hours of manual searching, so the people who understand the questions best are often the least able to reach the data.

**The challenge:** Create an AI-powered data experience that lets people ask questions in everyday language and get useful answers grounded in the available data, with enough explanation that users trust the response reflects the information actually examined.

**Our approach:** DataMind uses Gemma 3 4B through local Ollama inference to generate SQL, validates the generated SQL with SQLGlot AST parsing, and executes approved queries against Snowflake. Answers are constructed strictly from the returned rows, with the SQL, Snowflake query ID, sentence-level traceability claims, cost metrics, and data-quality checks available for verification.

---

## What it does

Most people who have business questions can't write SQL. DataMind bridges that gap.

You type something like *"Which 5 nations had the highest revenue last year?"* and the app:

1. Figures out what you're asking
2. Writes a SQL query for it
3. Runs that query on Snowflake
4. Explains the answer using only the actual rows returned

The model never makes up numbers. Every answer comes with the query that produced it, the rows it was built from, and the Snowflake query ID so you can verify it yourself.

---

## How it works

```
Your question
     ↓
Gemma (local) — understands the question, writes SQL
     ↓
sqlglot — checks the SQL is safe (read-only, allowed tables only)
     ↓
Snowflake — runs the query, returns real rows
     ↓
Gemma (local) — explains the rows in plain English
     ↓
You get: answer + SQL + rows + chart + query ID
```

Gemma handles the language. Snowflake handles the data. They never mix.

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- Ollama with Gemma 3 4B (`ollama pull gemma3:4b`)
- Snowflake account credentials

### 2. Environment Setup
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure credentials in `.env`:
```ini
SNOWFLAKE_ACCOUNT=.....
SNOWFLAKE_USER=....
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ROLE=SYSADMIN
SNOWFLAKE_WAREHOUSE=DATAMIND_WH
SNOWFLAKE_DATABASE=DATAMIND_DB
SNOWFLAKE_SCHEMA=PUBLIC
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
```

### 3. Launch the Application
Run the Streamlit web interface:
```bash
PYTHONPATH=. streamlit run app/streamlit_app.py
```
Open your browser at `http://localhost:8502`.

Or run via the CLI:
```bash
PYTHONPATH=. python -m datamind.cli "Which country had the highest primary value in 2020?"
```

### 4. Run Test Suite
```bash
PYTHONPATH=. pytest -v
```
All 12 unit tests verify chart selection, configuration loading, number grounding, data quality metrics, and SQL validation rules.

---

## Architecture and Evidence Pipeline

```
Question -> Local Gemma Router -> Local Gemma SQL Writer -> SQLGlot AST Validator
         -> Snowflake Execution -> Local Gemma Explainer -> Grounding Check -> UI Evidence Tabs
```

The model never connects directly to the database. Snowflake is the execution engine; local Gemma handles natural language translation, routing, and explanations.

Every answer presented in the UI is accompanied by four verification tabs:
1. **Query**: The validated read-only SQL executed on Snowflake.
2. **Rows & Chart**: The raw tabular results alongside an automatically chosen Altair visualization.
3. **Traceability & Cost**: Sentence-level claim attribution and estimated Snowflake credit usage.
4. **Data Quality**: Null counts, completeness metrics, and column distinct values.

---

## Datasets Supported

1. **DataMind DB (`DATAMIND_DB.PUBLIC.DATAMIND`)**:
   - 4,368 rows of global country-level annual measurements.
   - Columns: `ENTITY`, `CODE`, `YEAR`, `PRIMARY`.
   - Config: `configs/datamind_db.yaml`.

2. **TPC-H SF1 (`SNOWFLAKE_SAMPLE_DATA.TPCH_SF1`)**:
   - Industry-standard relational benchmark dataset.
   - Tables: `CUSTOMER`, `ORDERS`, `LINEITEM`, `NATION`, `REGION`.
   - Config: `configs/tpch.yaml`.

3. **User-Uploaded Datasets**:
   - Upload any CSV or Excel file via the sidebar to load it directly into Snowflake and query it immediately.
