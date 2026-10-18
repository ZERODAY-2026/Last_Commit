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
from datamind.snowflake_client import SnowflakeClient


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
    query_tab, rows_tab, details_tab = st.tabs(["Query", "Rows", "Details"])
    with query_tab:
        if evidence.sql:
            st.code(evidence.sql, language="sql")
            st.caption("Use the code block menu to copy the query.")
    with rows_tab:
        if evidence.rows:
            st.dataframe(evidence.rows, use_container_width=True, hide_index=True)
            chart = result_chart(evidence.rows)
            if chart:
                st.plotly_chart(chart, use_container_width=True)
    with details_tab:
        st.json(
            {
                "query_id": evidence.query_id,
                "runtime_ms": evidence.elapsed_ms,
                "row_count": len(evidence.rows),
                "status": evidence.status,
            }
        )


load_dotenv()
st.set_page_config(page_title="DataMind", page_icon="D", layout="wide")
st.markdown(Path("app/static/style.css").read_text(), unsafe_allow_html=True)

configs = sorted(p for p in Path("configs").glob("*.yaml") if not p.name.endswith(".example.yaml"))
if not configs:
    configs = sorted(Path("configs").glob("*.yaml"))
default_config = os.getenv("DATASET_CONFIG", "configs/tpch.yaml")
config_paths = [str(path) for path in configs]
if default_config not in config_paths:
    default_config = config_paths[0] if config_paths else "configs/tpch.yaml"

if "history" not in st.session_state:
    st.session_state.history = []
if "answers" not in st.session_state:
    st.session_state.answers = []

with st.sidebar:
    st.markdown("### DataMind")
    st.caption("The answer and its receipt")
    selected = st.selectbox(
        "Dataset",
        config_paths,
        index=config_paths.index(default_config) if default_config in config_paths else 0,
        format_func=lambda value: DatasetConfig.from_file(value).display_name,
    )
    if st.button("Clear history"):
        st.session_state.history = []
        st.session_state.answers = []
        st.rerun()
    if st.session_state.history:
        st.markdown("#### History")
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
    for column, example in zip(cols, examples):
        column.info(example)

for answer in st.session_state.answers:
    with st.chat_message("user"):
        st.write(answer["question"])
    with st.chat_message("assistant"):
        st.markdown(f'<div class="dm-answer"><h2>{answer["evidence"].answer}</h2></div>', unsafe_allow_html=True)
        if answer["evidence"].explanation:
            st.markdown("#### How I got this")
            st.write(answer["evidence"].explanation)
        _render_evidence(answer["evidence"])

question = st.chat_input(f"Ask about {config.display_name}")
if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.spinner("Running query"):
        evidence = DataMind(config, OllamaGemma(), SnowflakeClient()).answer(
            question, st.session_state.history[:-1]
        )
    st.session_state.history.append({"role": "assistant", "content": evidence.answer})
    st.session_state.answers.append({"question": question, "evidence": evidence})
    st.rerun()
