from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from dotenv import load_dotenv

from datamind.charts import result_chart
from datamind.config import DatasetConfig
from datamind.gemma_client import OllamaGemma
from datamind.orchestrator import DataMind
from datamind.quality import compute_data_quality, estimate_query_cost
from datamind.snowflake_client import SnowflakeClient
from datamind.uploader import upload_file_to_snowflake


def _render_evidence(evidence) -> None:
    status = "Verified" if evidence.status == "success" and not evidence.warning else evidence.status.title()
    st.markdown(
        f'<div class="dm-meta"><span class="dm-verified">{status}</span> · '
        f'{evidence.elapsed_ms} ms · {len(evidence.rows)} rows</div>',
        unsafe_allow_html=True,
    )
    for assumption in evidence.assumptions:
        st.markdown(f'<span class="dm-assumption">Assumed: {assumption}</span>', unsafe_allow_html=True)
    if evidence.warning:
        st.warning(evidence.warning)

    query_tab, rows_tab, trace_tab, quality_tab = st.tabs(
        ["Query", "Rows & Chart", "Traceability & Cost", "Data Quality"]
    )

    with query_tab:
        if evidence.sql:
            st.code(evidence.sql, language="sql")
            st.caption("Read-only validated Snowflake SQL statement.")

    with rows_tab:
        if evidence.rows:
            st.dataframe(evidence.rows, use_container_width=True, hide_index=True)
            chart = result_chart(evidence.rows)
            if chart:
                st.plotly_chart(chart, use_container_width=True)

    with trace_tab:
        wh = os.getenv("SNOWFLAKE_WAREHOUSE", "DATAMIND_WH")
        cost_info = estimate_query_cost(evidence.elapsed_ms, warehouse_size="XSMALL")
        col1, col2, col3 = st.columns(3)
        col1.metric("Query ID", evidence.query_id or "N/A")
        col2.metric("Latency", f"{evidence.elapsed_ms} ms")
        col3.metric("Est. Credits", f"{cost_info['estimated_credits']:.6f}")

        st.json(
            {
                "query_id": evidence.query_id,
                "runtime_ms": evidence.elapsed_ms,
                "row_count": len(evidence.rows),
                "status": evidence.status,
                "warehouse": wh,
                "role": os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
                "estimated_credit_usage": cost_info["estimated_credits"],
                "safeguards": "sqlglot AST read-only verified, DDL/DML blocked",
            }
        )

    with quality_tab:
        if evidence.rows:
            dq = compute_data_quality(evidence.rows)
            qcol1, qcol2, qcol3 = st.columns(3)
            qcol1.metric("Completeness", f"{dq['completeness_pct']}%")
            qcol2.metric("Total Cells", f"{dq['row_count'] * dq['total_columns']}")
            qcol3.metric("Null Count", f"{dq['null_cells']}")
            st.caption("Column profiling on returned result rows:")
            st.json(dq["columns"])
        else:
            st.info("No rows returned to profile.")


load_dotenv()
st.set_page_config(page_title="DataMind", page_icon="D", layout="wide")

configs = sorted(p for p in Path("configs").glob("*.yaml") if not p.name.endswith(".example.yaml"))
if not configs:
    configs = sorted(Path("configs").glob("*.yaml"))
default_config = os.getenv("DATASET_CONFIG", "configs/tpch.yaml")
config_paths = [str(path) for path in configs]

if "history" not in st.session_state:
    st.session_state.history = []
if "answers" not in st.session_state:
    st.session_state.answers = []

if "selected_dataset" in st.session_state and st.session_state.selected_dataset in config_paths:
    default_index = config_paths.index(st.session_state.selected_dataset)
elif default_config in config_paths:
    default_index = config_paths.index(default_config)
else:
    default_index = 0

with st.sidebar:
    st.markdown("### DataMind")
    st.caption("The answer and its receipt")

    selected = st.selectbox(
        "Active Dataset",
        config_paths,
        index=default_index,
        format_func=lambda value: DatasetConfig.from_file(value).display_name,
    )
    st.session_state.selected_dataset = selected

    with st.expander("Add Dataset (CSV / Excel)"):
        st.caption("Upload structured tabular or text data directly to Snowflake:")
        uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx", "xls"])
        ds_name = st.text_input("Dataset Display Name", placeholder="e.g. Sales Report 2026")
        if st.button("Upload to Snowflake", type="primary", use_container_width=True):
            if not uploaded_file:
                st.warning("Please choose a file to upload.")
            else:
                with st.spinner("Uploading table to Snowflake and generating connector..."):
                    sf_client = SnowflakeClient()
                    success, msg, new_cfg = upload_file_to_snowflake(
                        uploaded_file,
                        display_name=ds_name,
                        connection=sf_client._connect(),
                    )
                    if success:
                        st.success(msg)
                        st.session_state.selected_dataset = new_cfg
                        st.session_state.history = []
                        st.session_state.answers = []
                        st.rerun()
                    else:
                        st.error(msg)

    with st.expander("Schema Discovery"):
        st.caption("Auto-discover tables from Snowflake INFORMATION_SCHEMA:")
        disc_db = st.text_input("Database", value="DATAMIND_DB")
        disc_sch = st.text_input("Schema", value="PUBLIC")
        if st.button("Discover Schema", use_container_width=True):
            with st.spinner("Querying Snowflake catalog..."):
                try:
                    sf_client = SnowflakeClient()
                    discovered = DatasetConfig.discover_from_snowflake(
                        sf_client._connect(), disc_db, disc_sch
                    )
                    disc_file = f"configs/{disc_db.lower()}_{disc_sch.lower()}.yaml"
                    import yaml

                    cfg_dict = {
                        "dataset": discovered.name,
                        "display_name": discovered.display_name,
                        "description": discovered.description,
                        "snowflake": {"database": discovered.database, "schema": discovered.schema},
                        "tables": discovered.tables,
                        "joins": [],
                        "synonyms": {},
                        "metrics": {},
                        "examples": [],
                        "limits": {"max_rows": 1000},
                        "guardrails": {"max_rows": 1000, "allowed_tables": list(discovered.tables.keys()), "blocked_columns": []},
                    }
                    with open(disc_file, "w", encoding="utf-8") as f:
                        yaml.dump(cfg_dict, f, sort_keys=False, default_flow_style=False)
                    st.success(f"Discovered {len(discovered.tables)} table(s). Registered: {disc_file}")
                    st.session_state.selected_dataset = disc_file
                    st.rerun()
                except Exception as exc:
                    st.error(f"Discovery error: {exc}")

    with st.expander("Role-Based Access & Safeguards"):
        st.caption("Connected Session Info:")
        st.write(f"**User:** `{os.getenv('SNOWFLAKE_USER', 'N/A')}`")
        st.write(f"**Role:** `{os.getenv('SNOWFLAKE_ROLE', 'SYSADMIN')}`")
        st.write(f"**Warehouse:** `{os.getenv('SNOWFLAKE_WAREHOUSE', 'DATAMIND_WH')}`")
        st.write(f"**Safeguards:** `Read-Only AST (sqlglot)`")

    if st.button("Clear history", use_container_width=True):
        st.session_state.history = []
        st.session_state.answers = []
        st.rerun()

    if st.session_state.history:
        st.markdown("#### Conversation History")
        for item in st.session_state.history[::2]:
            st.caption(item["content"][:70])

config = DatasetConfig.from_file(selected)
st.markdown('<div class="dm-eyebrow">Trust tool for questions about data</div>', unsafe_allow_html=True)
st.title(config.display_name)
st.caption("Local Gemma writes and explains SQL. Snowflake computes the answer.")

if not st.session_state.history:
    st.markdown("Ask a question and check the result in seconds.")
    examples = [item["q"] for item in config.examples[:3]]
    if not examples:
        examples = ["How many orders were placed in 1995?", "Which nations had the highest revenue?"]
    cols = st.columns(len(examples))
    for c_idx, (column, example) in enumerate(zip(cols, examples)):
        if column.button(example, key=f"starter_q_{c_idx}", use_container_width=True):
            st.session_state.pending_question = example
            st.rerun()

for idx, answer in enumerate(st.session_state.answers):
    with st.chat_message("user"):
        st.write(answer["question"])
    with st.chat_message("assistant"):
        st.markdown(f'<div class="dm-answer"><h2>{answer["evidence"].answer}</h2></div>', unsafe_allow_html=True)
        if answer["evidence"].explanation:
            st.markdown("#### How I got this")
            st.write(answer["evidence"].explanation)
        _render_evidence(answer["evidence"])

        suggested = getattr(answer["evidence"], "suggested_questions", [])
        if suggested:
            st.markdown("##### Suggested questions you can ask:")
            for s_idx, sugg in enumerate(suggested):
                if st.button(sugg, key=f"sugg_{idx}_{s_idx}"):
                    st.session_state.pending_question = sugg
                    st.rerun()

question = st.chat_input(f"Ask about {config.display_name}")
pending_q = st.session_state.pop("pending_question", None)
if pending_q:
    question = pending_q

if question:
    with st.spinner("Running query"):
        evidence = DataMind(config, OllamaGemma(), SnowflakeClient()).answer(
            question, st.session_state.answers
        )
    st.session_state.history.append({"role": "user", "content": question})
    st.session_state.history.append({"role": "assistant", "content": evidence.answer})
    st.session_state.answers.append({"question": question, "evidence": evidence})
    st.rerun()
