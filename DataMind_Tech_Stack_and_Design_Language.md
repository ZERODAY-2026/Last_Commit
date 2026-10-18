@# DataMind: Tech Stack, Implementation Requirements and Design Language
ZeroDay OSS Hacktoberfest 2026 · PS1

This document is the build reference. It lists every technology we use, everything that must be in place before coding, how each piece is implemented, and the design language for the interface.

---

# Part A. Tech stack

## A1. Stack at a glance

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Best support for Snowflake, Gemma runtimes and data tooling |
| Data platform (required) | Snowflake | Stores data, executes all SQL |
| Model (required) | Google Gemma (3n E4B or Gemma 4 E4B) | Language tasks only: route, write SQL, explain |
| Model runtime | Ollama (primary), Hugging Face Transformers (fallback) | Ollama is the quickest local setup; HF gives full control |
| Snowflake driver | `snowflake-connector-python` | Simple, returns query IDs for evidence |
| SQL parsing and safety | `sqlglot` (Snowflake dialect) | Parse the model's SQL and enforce read-only rules without a model |
| Data validation | `pydantic` v2 | Strict JSON schemas for every Gemma output |
| Config | `pyyaml` + `python-dotenv` | Dataset config in YAML, secrets in `.env` |
| Data handling | `pandas` | Result frames, number checking, charts |
| Charts | `plotly` | Interactive charts from verified result rows |
| UI | Streamlit with custom CSS | Fast to build, flexible enough for the evidence panel |
| Testing | `pytest` | Golden questions, validator and number-check tests |
| Lint and format | `ruff` | One tool for both |
| Packaging | `pyproject.toml`, optional `Dockerfile` | Reproducible install |
| CI | GitHub Actions | Runs lint, unit tests and the validator tests on every push |
| Licence | Apache 2.0 (or MIT) | Open-source deliverable |

Pin exact versions in `requirements.txt` at install time. Gemma 3n needs Transformers 4.53.0 or later if you use Hugging Face.

## A2. Gemma setup

- **Variant:** start with Gemma 3n E4B. Try Gemma 4 E4B if it is available in your runtime. The guide reports Gemma 4 only from press coverage, so confirm its licence and tags on Google's official model card before relying on it.
- **Licence:** Gemma 3n weights are gated on Hugging Face and Kaggle and follow the Gemma Terms of Use. Accept the licence before downloading.
- **Runtime:** `ollama pull <gemma-tag>`, then call the local HTTP API (`http://localhost:11434`). Tag names change, so check the Ollama library.
- **Hardware:** an E4B model in a quantized build runs on a modern laptop with roughly 8 to 16 GB of RAM. If hardware is too weak, use E2B or a hosted Gemma endpoint (Vertex AI or AI Studio).
- **Settings:** temperature 0 to 0.2, JSON-only output, small max token limits for the router and SQL writer.
- **Features differ between variants, quantizations and runtimes.** Test the exact setup you will demo.

## A3. Snowflake setup

- Trial account at `signup.snowflake.com` (email only, 30 days or until credits run out).
- Confirm the account region and that `SNOWFLAKE_SAMPLE_DATA` is visible.
- We use **no Cortex AI Functions**, so the daily Cortex credit limit does not affect us and Gemma stays the only model.
- Setup script `scripts/setup_snowflake.sql`:

```sql
-- warehouse: tiny and self-suspending to save credits
CREATE WAREHOUSE IF NOT EXISTS DATAMIND_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- hard credit cap
CREATE RESOURCE MONITOR IF NOT EXISTS DATAMIND_MON
  WITH CREDIT_QUOTA = 20
  TRIGGERS ON 80 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE DATAMIND_WH SET RESOURCE_MONITOR = DATAMIND_MON;

-- own database for second dataset and logs
CREATE DATABASE IF NOT EXISTS DATAMIND_DB;
CREATE SCHEMA IF NOT EXISTS DATAMIND_DB.SECOND_DATASET;
CREATE SCHEMA IF NOT EXISTS DATAMIND_DB.AUDIT;

-- read-only role used by the app
CREATE ROLE IF NOT EXISTS DATAMIND_READER;
GRANT USAGE ON WAREHOUSE DATAMIND_WH TO ROLE DATAMIND_READER;
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE_SAMPLE_DATA TO ROLE DATAMIND_READER;
GRANT USAGE ON DATABASE DATAMIND_DB TO ROLE DATAMIND_READER;
GRANT USAGE ON SCHEMA DATAMIND_DB.SECOND_DATASET TO ROLE DATAMIND_READER;
GRANT SELECT ON ALL TABLES IN SCHEMA DATAMIND_DB.SECOND_DATASET TO ROLE DATAMIND_READER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA DATAMIND_DB.SECOND_DATASET TO ROLE DATAMIND_READER;

-- app user
CREATE USER IF NOT EXISTS DATAMIND_APP
  DEFAULT_ROLE = DATAMIND_READER
  DEFAULT_WAREHOUSE = DATAMIND_WH;
GRANT ROLE DATAMIND_READER TO USER DATAMIND_APP;
```

Datasets: TPC-H is referenced in place inside `SNOWFLAKE_SAMPLE_DATA` and never copied into the repo. The second dataset (UCI or Our World in Data) is loaded into `DATAMIND_DB.SECOND_DATASET` by `scripts/load_second_dataset.py`. Check each dataset's licence and add attribution.

---

# Part B. Everything required before implementation

## B1. Accounts, access and installs checklist

- [ ] Snowflake trial account created, region noted
- [ ] `SNOWFLAKE_SAMPLE_DATA` queries run in a worksheet (`SELECT COUNT(*) FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS`)
- [ ] Setup script run, `DATAMIND_READER` role works
- [ ] Gemma licence accepted (Hugging Face or Kaggle) if you download weights directly
- [ ] Ollama installed, Gemma model pulled, one test prompt answered
- [ ] Python 3.11+, `git`, virtual environment
- [ ] GitHub repository created with the licence file
- [ ] Second dataset chosen and its licence read
- [ ] A plan to keep evidence if the trial expires (screenshots, video, saved query logs)

## B2. Environment variables (`.env.example`)

```
SNOWFLAKE_ACCOUNT=xxxx-yyyy
SNOWFLAKE_USER=DATAMIND_APP
SNOWFLAKE_PASSWORD=change_me        # or key-pair auth variables
SNOWFLAKE_ROLE=DATAMIND_READER
SNOWFLAKE_WAREHOUSE=DATAMIND_WH
DATASET_CONFIG=configs/tpch.yaml
GEMMA_BACKEND=ollama                # ollama | hf
GEMMA_MODEL=<your-gemma-tag>
OLLAMA_URL=http://localhost:11434
MAX_ROWS=1000
QUERY_TIMEOUT_SECONDS=30
```

Never commit `.env`. Key-pair auth is preferred over passwords if time allows.

## B3. Dataset config contract (`configs/*.yaml`)

Every dataset is described by one file. The code reads only this, so a new dataset needs no code changes.

```yaml
dataset: tpch
display_name: TPC-H Sales
snowflake:
  database: SNOWFLAKE_SAMPLE_DATA
  schema: TPCH_SF1
tables:
  ORDERS:
    description: One row per customer order
    columns:
      O_ORDERKEY:   {type: NUMBER, description: order id}
      O_CUSTKEY:    {type: NUMBER, description: customer id}
      O_ORDERDATE:  {type: DATE,   description: date the order was placed}
      O_TOTALPRICE: {type: NUMBER, description: order total}
  LINEITEM: { ... }
  CUSTOMER: { ... }
joins:
  - ORDERS.O_CUSTKEY = CUSTOMER.C_CUSTKEY
  - LINEITEM.L_ORDERKEY = ORDERS.O_ORDERKEY
metrics:                      # business words the user may say
  revenue: "SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT))"
synonyms:
  customers: [clients, buyers]
  orders: [purchases]
examples:                     # few-shot pairs for the SQL writer
  - q: "Top 5 nations by revenue in 1995"
    sql: "SELECT ..."
guardrails:
  max_rows: 1000
  allowed_tables: [ORDERS, LINEITEM, CUSTOMER, NATION, REGION, PART, SUPPLIER]
  blocked_columns: []         # e.g. personal data
```

## B4. Data contracts between modules (Pydantic)

```python
class RouterOutput(BaseModel):
    intent: Literal["answerable", "ambiguous", "unsupported", "follow_up"]
    clarifying_question: str | None = None
    reason: str

class SqlOutput(BaseModel):
    sql: str
    assumptions: list[str]
    tables_used: list[str]

class Evidence(BaseModel):
    question: str
    sql: str
    snowflake_query_id: str
    rows: list[dict]
    row_count: int
    truncated: bool
    runtime_ms: int
    assumptions: list[str]
    warnings: list[str]

class Answer(BaseModel):
    summary: str
    how_obtained: str
    evidence: Evidence
    numbers_verified: bool
```

Every Gemma call must return JSON that parses into one of these. If parsing fails, retry once, then fail with a clear message.

---

# Part C. How each part is implemented

## C1. Request flow

```
1. Receive question + chat history
2. Router (Gemma)        -> answerable / ambiguous / unsupported / follow_up
3. If ambiguous          -> show clarifying question, stop
4. If unsupported        -> explain what is not in the data, stop
5. SQL writer (Gemma)    -> SqlOutput
6. Validator (sqlglot)   -> pass or reject with reason
7. Execute (Snowflake)   -> rows + query ID
8. On SQL error          -> send error to SQL writer, retry (max 2)
9. If zero rows          -> honest empty-result message with the filters used
10. Explainer (Gemma)    -> summary + how_obtained, from rows only
11. Number check         -> every number in summary must appear in rows
12. Render answer + evidence panel + optional chart
13. Write audit log row (question, SQL, query ID, status)
```

## C2. Validator rules (no model involved)

Reject unless all are true:
- Exactly one statement
- Statement type is `SELECT` (or `WITH ... SELECT`)
- No DDL, DML, `COPY`, `PUT`, `GET`, `CALL`, `USE`, or `SET`
- Every table is in `allowed_tables` and resolves to the configured database and schema
- No blocked columns
- A `LIMIT` exists, or one is added (never above `max_rows`)

The `DATAMIND_READER` role is the second line of defence, so a validator bug cannot write data.

## C3. Prompts (kept in `datamind/prompts/`)

- **router.md:** schema summary, the user question, the last turn if any. Output the `RouterOutput` JSON only.
- **sql_writer.md:** full schema with descriptions, joins, metric definitions, synonyms, 3 to 6 examples, Snowflake SQL dialect notes, rule "use only listed tables and columns", output `SqlOutput` JSON only.
- **explainer.md:** the question, the executed SQL, the result rows. Rules: use only values present in the rows, state assumptions, mention truncation, do not speculate on causes.

## C4. Number check

1. Extract numbers from the summary (handle commas, percent signs, decimals, rounding).
2. Check each against values in the result rows or a simple derived value (sum, difference, percent of a total that appears in the rows).
3. If a number is unmatched, regenerate the explanation once. If it still fails, show the raw rows and a warning, not the unverified summary.

## C5. Follow-up handling

Store the last question, the executed SQL and a short result summary in session state. For a follow-up, pass these to the router and SQL writer so "and only for Europe?" becomes a modified version of the previous query.

## C6. Charts

Choose the chart from column types in the verified result: one category plus one measure gives a bar chart, a date plus a measure gives a line chart, otherwise only a table. Charts always come from the result rows, never from model-written numbers.

## C7. Audit and cost log

Write one row per question to `DATAMIND_DB.AUDIT.QUERY_LOG` with timestamp, question, SQL, query ID, status, runtime and retry count. This supports traceability and the cost and reliability panel.

## C8. Repository layout

```
datamind/
├── README.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .streamlit/config.toml
├── docs/
│   ├── architecture.md
│   ├── adding_a_dataset.md
│   └── design_language.md
├── configs/
│   ├── tpch.yaml
│   └── second_dataset.yaml
├── datamind/
│   ├── config.py
│   ├── snowflake_client.py
│   ├── gemma_client.py
│   ├── schemas.py
│   ├── router.py
│   ├── sql_writer.py
│   ├── validator.py
│   ├── explainer.py
│   ├── number_check.py
│   ├── orchestrator.py
│   ├── charts.py
│   ├── audit.py
│   └── prompts/
├── app/
│   ├── streamlit_app.py
│   ├── components/
│   └── static/style.css
├── scripts/
│   ├── setup_snowflake.sql
│   └── load_second_dataset.py
└── tests/
    ├── golden_questions.yaml
    ├── test_validator.py
    ├── test_number_check.py
    ├── test_router.py
    └── test_end_to_end.py
```

## C9. Testing plan

- **Golden set:** 30 to 50 questions with independently written ground-truth SQL and stored expected results. Cover single-table, multi-table joins, ranking, date filters, group-by, multi-step, and at least 10 paraphrases of the same question.
- **Guardrail tests:** destructive requests, out-of-scope questions, ambiguous questions, empty results, injection-style input.
- **Change test:** insert or update a row in the second dataset and confirm the answer changes.
- **Reusability test:** run the golden flow against the second dataset using only a different `DATASET_CONFIG`.
- **Metric:** percentage of golden questions matching ground truth, tracked after every prompt change.

## C10. Run commands (README quick start)

```bash
git clone <repo> && cd datamind
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in credentials
# run scripts/setup_snowflake.sql in a Snowflake worksheet
ollama pull <gemma-tag>
streamlit run app/streamlit_app.py
pytest
```

---

# Part D. Design language

## D1. Subject, audience, job

- **Subject:** a trust tool for questions about data.
- **Users:** analysts, operations managers, researchers and students who know their questions but not SQL.
- **Primary job:** get an answer and be able to check it in seconds.
- **Judges' angle:** visual polish earns little, so the design spends its effort on legibility and proof.

## D2. Concept: "the answer and its receipt"

The interface looks like a careful analyst's workbook, not a chat toy. Every answer arrives with its receipt attached: the query, the rows and the assumptions. The memorable moment is **claim linking**: hover or tap any number in the answer and the matching row in the result table and the matching clause in the SQL light up together. That one interaction shows the system is grounded. Everything else stays quiet.

## D3. Color tokens

| Token | Hex | Use |
|---|---|---|
| `--paper` | `#F3F6F8` | Page background (cool, slightly blue-grey) |
| `--surface` | `#FFFFFF` | Answer and evidence panels |
| `--ink` | `#16222C` | Primary text |
| `--ink-soft` | `#52616D` | Secondary text, table headers |
| `--teal` | `#0E6B72` | Primary actions, links, claim highlight |
| `--verified` | `#2F7D57` | Number check passed, query succeeded |
| `--assumption` | `#B7791F` | Assumptions, truncation, clarifications |
| `--error` | `#B23A2C` | Failed query, refused request |
| `--highlight` | `#CDE9EB` | Linked claim, row and SQL clause highlight |
| `--rule` | `#D5DDE3` | Dividers and table lines |

Dark mode: invert surfaces to `#0F1A22` (paper) and `#16242E` (surface), text `#E6EDF2`, keep the same semantic hues lightened for contrast. Meaning never relies on color alone: status also carries an icon and a word.

## D4. Typography

| Role | Typeface | Notes |
|---|---|---|
| Answer text | Newsreader (serif) | Slightly larger, generous line height, so the answer reads like a finding |
| Interface | Instrument Sans | Buttons, labels, navigation, tables |
| SQL and identifiers | JetBrains Mono | Only for SQL, column names and query IDs |

All three have open licences on Google Fonts. Provide system fallbacks (`Georgia`, `system-ui`, `ui-monospace`).

Scale (rem): 0.8125 (meta), 0.9375 (UI body), 1.0625 (table), 1.25 (answer), 1.75 (answer figure), 2.25 (page title). Keep lines under 75 characters. Use sentence case everywhere. No all-caps labels.

## D5. Layout

Desktop, three regions:

```
+-------------+-----------------------------------+----------------------+
| Dataset     |  Conversation                      |  Evidence            |
|             |                                    |                      |
| TPC-H Sales |  You: top 5 nations by revenue     |  Query   [Copy]      |
|  v          |                                    |  SELECT n_name, ...  |
|             |  Answer (serif, large)             |                      |
| History     |  "Russia led with 41.2M ..."       |  Rows (5)            |
|  - q1       |   ^ numbers are linked to evidence |  n_name | revenue    |
|  - q2       |                                    |  ...                 |
|             |  How I got this                    |  Assumptions         |
| Settings    |  Tables, filters, assumptions      |  Query ID, 340 ms    |
+-------------+-----------------------------------+----------------------+
| Ask about TPC-H Sales...                                     [Ask]      |
+-------------------------------------------------------------------------+
```

- Left rail is narrow and collapsible. It holds the dataset switcher (driven by the config files) and history.
- The conversation column is left aligned, max width about 44 rem.
- The evidence panel is a persistent right column on wide screens and a bottom sheet on mobile.
- Alignment: all text left aligned. Numeric table columns right aligned with tabular figures.

Mobile: single column, answer first, evidence as an expandable sheet pinned under the answer.

## D6. Components

**Answer block.** The finding in serif type with key figures at a larger size. Beneath it, a one-line status: "Checked: 5 of 5 numbers match the rows" with a verified icon.

**How I got this.** Plain-language list of tables used, filters, joins and assumptions. Written from the user's view ("I added up revenue for 1995 orders and ranked nations"), not the system's.

**Evidence panel.** Tabs: Query, Rows, Details. Query shows syntax-highlighted SQL with a copy button. Rows shows a sortable table. Details shows Snowflake query ID, runtime, row count, retries and warnings.

**Claim linking.** Numbers in the answer are underlined with a thin teal line. On hover or focus they get the `--highlight` background, and the matching row and SQL clause get the same background. Works with keyboard focus and touch.

**Assumption chip.** Amber outline with an icon and short text, such as "Assumed 'best' means highest revenue". The user can click it to choose another meaning, which re-runs the query.

**Clarifying question.** When the router returns ambiguous, show the question with 2 to 4 answer buttons and a text field. No query runs until the user picks.

**Chart.** Shown only when the result suits it, built from the rows. Single hue (teal) by default, labelled axes, a "Show data" toggle that opens the same rows table.

**Status chip.** Icon plus word: Verified, Assumed, Truncated, Failed, Refused.

## D7. Shape, spacing and depth

- 4 px spacing grid.
- Panels use a 1 px `--rule` border and no shadow. Depth comes from borders and background contrast.
- Radius is varied on purpose: 2 px for tables and code, 6 px for buttons and chips, 10 px for panels.
- Dense, readable tables: 36 px rows, tabular numerals, sticky header.

## D8. Motion

- One orchestrated moment: when an answer completes, the status line resolves from "Running query" to "Checked" and the linked numbers underline once.
- Responding to actions only: expand and collapse of the evidence panel, claim highlight on hover, copy confirmation.
- No entrance animation on sections or cards. Respect `prefers-reduced-motion`.

## D9. Voice and copy

- Plain verbs, sentence case, active voice. Name things by what users understand ("Show the query", not "Inspect SQL artifact").
- Buttons say what happens: "Ask", "Copy query", "Use this meaning".
- Same word for the same thing throughout: always "query" and "rows", never mixed with "statement" or "records".
- Errors say what failed and what to do, with no apology. Example: "No rows matched. The filters were: year = 2031, region = Europe. Try a different year."
- Refusals state the reason: "This tool only reads data. It cannot change or delete rows."
- Empty start screen invites action with three example questions drawn from the active dataset config.

## D10. Accessibility floor

- Text contrast of at least 4.5:1, check both light and dark modes.
- Visible keyboard focus on every control, including linked numbers.
- Status never conveyed by color alone.
- Tables have proper header cells; charts have a text summary and the "Show data" toggle.
- Responsive down to 360 px width.

## D11. Streamlit implementation notes

`.streamlit/config.toml`:

```toml
[theme]
base = "light"
primaryColor = "#0E6B72"
backgroundColor = "#F3F6F8"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#16222C"
font = "sans serif"
```

Load fonts and custom styles from `app/static/style.css` through `st.markdown(..., unsafe_allow_html=True)`. Define the color tokens as CSS variables on `:root` and override them inside `@media (prefers-color-scheme: dark)`. Claim linking is built with a small custom component or `st.components.v1.html` that shares a selected row ID with the table and SQL display. If Streamlit limits this interaction, a fallback is clickable "Evidence" links next to each number that scroll to and highlight the row.

If the UI later outgrows Streamlit, the backend (`orchestrator.py`) is framework-free, so a FastAPI plus React front end can replace it without touching the data or model code.

---

# Part E. Delivery order

1. Accounts, installs, Snowflake setup script, Gemma test call.
2. `config.py`, `snowflake_client.py`, `gemma_client.py`, schemas.
3. Router, SQL writer, validator, execution on TPC-H through a CLI.
4. Explainer, number check, evidence object, audit log.
5. Streamlit UI with answer block, evidence panel and claim linking.
6. Ambiguity, empty results, unsupported requests, follow-ups, charts.
7. Second dataset by config only.
8. Golden tests and tuning.
9. README, architecture doc, demo video and screenshots.

If time runs short, finish steps 1 to 6 and step 8 first. Correct, traceable answers decide the score.
