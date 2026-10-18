# PS-1 DataMind: Talk to Your Data

## Problem Statement
Organizations hold large amounts of information in databases, spreadsheets, documents, and other sources. Getting a useful answer often takes technical skills, specialized queries, or hours of manual searching, so the people who understand the questions best are often the least able to reach the data.

**The challenge:** Create an AI-powered data experience that lets people ask questions in everyday language and get useful answers grounded in the available data, with enough explanation that users trust the response reflects the information actually examined.

**Our approach:** DataMind uses Gemma 3 4B through local Ollama inference to generate SQL, validates the generated SQL with SQLGlot AST parsing, and executes approved queries against Snowflake. Answers are constructed strictly from the returned rows, with the SQL, Snowflake query ID, sentence-level traceability claims, cost metrics, and data-quality checks available for verification.

---

## Implemented Features Checklist

All core and advanced capabilities have been implemented, tested, and integrated:

- [x] **Query Validation and Read-Only Safeguards (#1)**
  - AST-based SQL validation using `sqlglot` (`datamind/validator.py`).
  - Strict read-only enforcement: rejects DDL/DML (`DROP`, `ALTER`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `COPY`).
  - Multi-statement blocking and automatic `LIMIT` clause enforcement.
  - Role-based Snowflake warehouse isolation.

- [x] **Answer-to-Query Traceability (#2)**
  - Sentence-level claim attribution mapping every claim in the explanation to specific row numbers and column names (`datamind/schemas.py`).
  - Evidence receipt containing exact query runtime, Snowflake query ID, and execution metadata.

- [x] **Follow-Up Questions with Conversational Context (#3)**
  - Multi-turn state tracking retaining previous questions, executed SQL, and result rows (`datamind/conversation.py`).
  - Intelligent entity and filter resolution (e.g., resolving relative pronouns like "these same 5 countries" or "those same nations").
  - SQL unified diff generation between consecutive turns.

- [x] **Visualizations Built from Verified Results (#4)**
  - Automatic chart generation via Altair (`datamind/charts.py`).
  - Smart visualization selection: line charts for time-series/years, bar charts for categorical distributions, and grouped charts for multi-dimensional data.
  - Interactive chart and raw data inspection inside the "Rows & Chart" evidence tab.

- [x] **Interactive Question Suggestions for Out-of-Scope Queries**
  - Automatic suggestion engine triggered when questions cannot be answered, are out-of-scope, or return zero rows (`datamind/gemma_client.py`).
  - Clickable one-click UI buttons allowing users to immediately execute suggested alternative questions.

- [x] **Dynamic Schema Discovery (#5)**
  - Automated inspection of Snowflake `INFORMATION_SCHEMA.COLUMNS` (`datamind/discovery.py`).
  - Generates dataset configuration YAML files dynamically without manual schema authoring.
  - Accessible via both Streamlit UI sidebar and CLI script (`scripts/discover_schema.py`).

- [x] **Automated Data-Quality Checks (#6)**
  - Computes completeness percentages, null count, and distinct value cardinality on returned query rows (`datamind/quality.py`).
  - Displays automated data hygiene summaries in the "Data Quality" tab.

- [x] **Cost and Reliability Monitoring (#7)**
  - Snowflake warehouse credit consumption estimation based on execution runtime and warehouse sizing (`datamind/quality.py`).
  - Query elapsed time tracking and audit logging (`datamind/audit.py`).

- [x] **Role-Based Access Control (RBAC) (#8)**
  - Session role indicators and security posture display in UI sidebar.
  - Dedicated role setup script (`scripts/setup_roles.sql`) supporting `DATAMIND_ANALYST` and `DATAMIND_VIEWER` roles.

- [x] **Multi-Step Analysis & Common Table Expressions (#9)**
  - Analytical step planner capable of decomposing complex questions into Common Table Expressions (CTEs) (`datamind/planner.py`).
  - Supports multi-level aggregations, ranking comparisons, and percentage-of-total calculations.

- [x] **Reusable Connectors and Multiple Formats (#10, #11)**
  - Abstract data connector interface (`datamind/connectors/base.py`).
  - In-browser file uploader (`datamind/uploader.py`) supporting CSV, XLSX, and XLS formats directly into Snowflake tables.
  - Auto-registration of uploaded tables into active dataset configurations.

- [x] **Structured Plus Unstructured Data (#12)**
  - Case-insensitive substring matching (`ILIKE '%term%'`) across descriptive entity columns.
  - Tolerates fuzzy entity naming, country names, and variations without strict equality constraints.

- [x] **Multilingual Natural Explainer**
  - Generates natural, complete sentences answering the question in the user's exact input language (English, Hindi, Hinglish, etc.).
  - Distinguishes language tags (e.g., "in hindi") from data filter predicates.

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
