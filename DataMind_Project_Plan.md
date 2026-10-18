




# DataMind: Talk to Your Data — Project Plan
ZeroDay OSS Hacktoberfest 2026 · PS1

---

## 1. What the problem is (in plain words)

People who understand the business questions usually cannot write SQL. We must build a system where a user types a normal question ("Which region had the highest revenue last year?") and gets:

1. A correct answer **computed from real data in Snowflake** at question time.
2. A plain-language explanation of how it was computed.
3. Proof: the executed SQL, the result rows, and any assumptions or gaps.

It must **not** be a chatbot that writes plausible text. The numbers must come from running a query.

### Hard requirements
| Requirement | What we do |
|---|---|
| Snowflake (required) | All data is stored and queried in Snowflake with SQL. Never answer from local files or mocks. |
| Gemma (required) | Gemma does the language work: understand the question, write SQL, explain results. Must be Gemma, not a Snowflake Cortex model. |
| Separation | Gemma = reasoning. Snowflake = data + execution. They never mix. |
| Open source | Public repo with code, setup guide, dependencies, architecture doc. Second dataset must work by **config change only**. |

### Scoring that matters most (100 pts)
- Correct answers on unseen questions: **20** (if this is poor, the total is capped at 50)
- Evidence / traceability: **15**
- Snowflake integration: **15**
- Gemma integration: **12**
- Ambiguity / errors / refusals: **12**
- NL interaction quality: **10**
- Reusability: **8**
- Practical UX: **8**

So: **correctness and evidence beat visual polish.**

---

## 2. The answer: our solution in one paragraph

A text-to-SQL **data agent**. The user asks a question. A Gemma model, given a compact schema description of the dataset, decides whether the question is answerable, ambiguous, or unsupported, and produces a SQL query. A deterministic validator checks that the query is safe (read-only, allowed tables only). The query runs on Snowflake. The returned rows go back to Gemma, which writes a short explanation using **only** those rows. The UI shows answer + explanation + SQL + rows + chart. A checker verifies that every number in the answer appears in the result rows.

---

## 3. Architecture

```
 User question (natural language)
        │
        ▼
 ┌───────────────┐
 │  UI (Streamlit)│  chat, evidence panel, charts
 └──────┬────────┘
        ▼
 ┌─────────────────────────────────────────────┐
 │ Orchestrator (Python)                        │
 │  1. Load dataset config (schema, joins, hints)│
 │  2. Intent step ──► Gemma                     │
 │  3. SQL generation ─► Gemma                   │
 │  4. Validator (sqlglot, deterministic)        │
 │  5. Execute ───────► Snowflake                │
 │  6. Repair loop (max 2) on SQL errors ► Gemma │
 │  7. Explain from rows ► Gemma                 │
 │  8. Number check (answer vs rows)             │
 └──────┬──────────────────────┬───────────────┘
        ▼                      ▼
  Gemma (Ollama / HF)     Snowflake (read-only role,
  inference only          X-SMALL warehouse)
```

**Golden rule:** Gemma never sees the database connection and never executes anything. Snowflake never runs a model.

### Component details

**3.1 Data layer (Snowflake)**
- Primary dataset: `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` (customers, orders, lineitem, part, supplier, nation, region). Joins and aggregates are easy to verify. Reference it in place, do not copy it into the repo (licence).
- Second dataset (proves reusability): a real-world one loaded into our own database, e.g. a UCI dataset (Bank Marketing / Student Performance) or Our World in Data indicators (country-year, with gaps for missing-data tests). Include only what the licence allows, with attribution.
- Roles: create `DATAMIND_READER` with SELECT-only on the allowed schemas. The app connects only with this role.
- Warehouse: X-SMALL, auto-suspend 60 s, resource monitor with a credit cap.

**3.2 Semantic / config layer (the key to reusability)**
One YAML file per dataset, e.g. `configs/tpch.yaml`:
```yaml
dataset: tpch
snowflake:
  database: SNOWFLAKE_SAMPLE_DATA
  schema: TPCH_SF1
tables:
  ORDERS:
    description: One row per customer order
    columns:
      O_ORDERDATE: {type: DATE, description: order date}
      O_TOTALPRICE: {type: NUMBER, description: order total in USD}
joins:
  - ORDERS.O_CUSTKEY = CUSTOMER.C_CUSTKEY
synonyms:
  revenue: "SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT))"
limits: {max_rows: 1000}
```
Schema can also be auto-discovered from `INFORMATION_SCHEMA` and merged with these hand-written descriptions. Swapping datasets = swapping this file.

**3.3 Gemma layer**
- Variant: Gemma 3n E4B or Gemma 4 E4B (confirm on the official model card; test your exact quantization and runtime).
- Hosting: Ollama locally (simplest) or Hugging Face Transformers. Document hardware needs.
- Three narrow tasks, each with its own prompt and a JSON output schema:
  1. **Router:** `answerable | ambiguous | unsupported | follow_up`, plus a clarifying question if ambiguous.
  2. **SQL writer:** schema-in-prompt + few-shot examples → one SELECT statement + list of assumptions.
  3. **Explainer:** rows + SQL → short answer and "how I got this", forbidden from adding facts not in the rows.
- Temperature 0–0.2. Parse and validate JSON; retry once on malformed output.

**3.4 Validation and safety (deterministic, no model)**
- Parse with `sqlglot` (Snowflake dialect).
- Allow only a single `SELECT` / `WITH ... SELECT`. Block DDL, DML, `COPY`, `PUT`, multiple statements, comments tricks.
- Table allowlist from config. Force `LIMIT`.
- Optional dry check with `EXPLAIN` before running.
- Read-only role is the second line of defence.

**3.5 Trust layer**
- **Number check:** extract numbers from the final answer and confirm each one exists in the result rows (or is a simple derived value). If not, regenerate or flag.
- **Empty result:** say "no rows matched these filters" and show the filters, do not invent an answer.
- **Truncation notice** when `max_rows` is hit.
- **Answer change test:** same question after data changes returns the new value (no caching of answers, only of schema).

---

## 4. How each mandatory requirement is met

| ID | Requirement | Implementation |
|---|---|---|
| M1 | Everyday-language questions | Gemma router + SQL writer with synonyms, few-shot variety |
| M2 | Real query at question time | Every answer triggers a live Snowflake query |
| M3 | Grounded, no unsupported claims | Explainer sees only rows; number check |
| M4 | Plain-language explanation | "How I got this": tables, filters, joins, assumptions |
| M5 | Inspectable evidence | Evidence panel: SQL, Snowflake query ID, rows, row count, runtime |
| M6 | Ambiguity, missing data, unsupported | Router clarifies; empty-result handler; refusal for writes/out-of-scope |
| M7 | Snowflake + Gemma | Sections 3.1 and 3.3 |
| M8 | Reproducible, open source | Repo with README, `requirements.txt`, setup scripts, docs, tests |

---

## 5. Optional features worth adding (in priority order)

1. Follow-up questions with context (keep last question, SQL, and result summary in the prompt).
2. Charts built from the verified result rows (bar/line chosen by column types).
3. Query validation and read-only safeguards (already in core).
4. Schema discovery from `INFORMATION_SCHEMA`.
5. Data-quality hints (null counts, date range shown next to answers).
6. Cost/reliability panel: query time, credits estimate, retry counts.
7. Multi-step analysis (break a complex question into 2–3 SQL steps).
8. Cortex Search for any text columns (optional, only if region supports it).

---

## 6. Repository structure

```
datamind/
├── README.md                 # setup, run, demo
├── docs/
│   ├── architecture.md       # diagrams, Snowflake + Gemma usage
│   └── adding_a_dataset.md
├── configs/
│   ├── tpch.yaml
│   └── second_dataset.yaml
├── datamind/
│   ├── config.py             # load YAML, schema discovery
│   ├── snowflake_client.py   # connection, execute, query ID
│   ├── gemma_client.py       # Ollama / HF wrapper
│   ├── prompts/              # router.md, sql_writer.md, explainer.md
│   ├── router.py
│   ├── sql_writer.py
│   ├── validator.py          # sqlglot checks
│   ├── explainer.py
│   ├── number_check.py
│   ├── orchestrator.py
│   └── charts.py
├── app/streamlit_app.py
├── scripts/
│   ├── setup_snowflake.sql   # role, warehouse, resource monitor
│   └── load_second_dataset.py
├── tests/
│   ├── golden_questions.yaml # question + independently computed answer
│   ├── test_validator.py
│   ├── test_number_check.py
│   └── test_end_to_end.py
├── requirements.txt
├── .env.example
└── LICENSE
```

---

## 7. Build plan (phases)

| Phase | Goal | Deliverable |
|---|---|---|
| 0 | Accounts and access | Snowflake trial, Gemma running locally, test one query and one prompt |
| 1 | Skeleton | Connection, config loader, `setup_snowflake.sql`, Gemma wrapper |
| 2 | Core loop | Question → SQL → validate → execute → rows (no UI yet, CLI) |
| 3 | Explanation + evidence | Explainer, number check, evidence object (SQL, rows, query ID) |
| 4 | UI | Streamlit chat with evidence panel and charts |
| 5 | Edge cases | Ambiguity, empty results, unsupported/unsafe, follow-ups |
| 6 | Second dataset | Add YAML + load script, fix any hard-coded assumptions |
| 7 | Testing | 30–50 golden questions, ground truth computed by hand-written SQL |
| 8 | Docs and demo | README, architecture doc, demo video, screenshots (offline evidence in case trial expires) |

If time is short, finish phases 0–5 and 7 first. Correctness beats extra features.

---

## 8. Testing strategy

**Golden set (most important).** For each test question, write the ground-truth SQL yourself and store the expected result. Cover:
- Single-table aggregates ("total orders in 1995")
- Multi-table joins ("top 5 nations by revenue")
- Rankings, filters, date ranges, group-by
- Multi-step ("which of the top 10 customers also ordered in Q4?")
- Paraphrases of the same question (10+ phrasings)

**Guardrail tests**
- "Delete all orders" → refused
- "Show me employee salaries" (not in data) → says unsupported
- "Best customers" → asks what "best" means (revenue? count?) or states assumption
- Filter that returns nothing → honest empty-result message
- SQL injection style inputs → blocked by validator

**Metric:** % of golden questions where our result equals ground truth. Track it per prompt change.

---

## 9. Credit and cost control

- X-SMALL warehouse, `AUTO_SUSPEND = 60`, `AUTO_RESUME = TRUE`.
- Resource monitor capped well below trial credit.
- Cache schema metadata, never cache answers.
- Gemma runs locally, so it uses no Snowflake credits (avoid Cortex AI Functions).
- Keep trial active through judging, or record demo evidence.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Small Gemma writes wrong SQL | Compact schema prompt, few-shot examples, repair loop, golden-set tuning |
| Hallucinated numbers in explanation | Explainer sees only rows; number check |
| Gemma 4 details unconfirmed | Check the official model card; fall back to Gemma 3n |
| Local hardware too weak | Use E2B/quantized build, or hosted Gemma endpoint (Vertex AI / AI Studio) |
| Trial expires before judging | Record video, save query logs and screenshots |
| Hard-coded to TPC-H | All table knowledge lives in YAML; test the second dataset early |
| Licence problems | Reference TPC-H in place; attribute OWID/UCI data |

---

## 11. Demo script (for judges)

1. Ask a simple aggregate. Show answer, SQL, rows, query ID.
2. Ask a join + ranking question phrased casually.
3. Ask a follow-up ("and only for Europe?").
4. Ask an ambiguous question → system clarifies.
5. Ask something unsupported / destructive → refused.
6. Switch config to the second dataset → ask a question without code changes.
7. Show the golden-test pass rate.

---

## 12. Definition of done

- [ ] Every answer comes from a live Snowflake query
- [ ] Every answer shows SQL, rows, and explanation
- [ ] Gemma is used for router, SQL, and explanation, separate from execution
- [ ] Read-only validator and role in place
- [ ] Ambiguous, empty, and unsupported cases handled
- [ ] Second dataset works via config only
- [ ] Golden tests pass at a high rate
- [ ] README, architecture doc, and setup scripts let a stranger reproduce it
