from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from snowflake.connector.pandas_tools import write_pandas


def clean_identifier(name: str) -> str:
    """Sanitize string to a valid Snowflake identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_").upper()
    if not cleaned or cleaned[0].isdigit():
        cleaned = "T_" + cleaned
    return cleaned


def infer_column_type(dtype: Any) -> str:
    """Map pandas dtype to DataMind schema type."""
    dtype_str = str(dtype).lower()
    if "int" in dtype_str or "float" in dtype_str or "decimal" in dtype_str:
        return "NUMBER"
    if "date" in dtype_str or "time" in dtype_str:
        return "DATE"
    if "bool" in dtype_str:
        return "BOOLEAN"
    return "TEXT"


def upload_file_to_snowflake(
    uploaded_file: Any,
    display_name: str,
    connection: Any,
    configs_dir: str = "configs",
) -> tuple[bool, str, str | None]:
    """Load a CSV or Excel file into Snowflake DATAMIND_DB and generate a DataMind config YAML.

    Returns:
        (success: bool, message: str, config_path: str | None)
    """
    try:
        filename = getattr(uploaded_file, "name", "uploaded_dataset")
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)

        if df.empty:
            return False, "The uploaded file is empty.", None

        cleaned_columns = {}
        for col in df.columns:
            clean_col = clean_identifier(str(col))
            counter = 1
            original_clean = clean_col
            while clean_col in cleaned_columns.values():
                clean_col = f"{original_clean}_{counter}"
                counter += 1
            cleaned_columns[col] = clean_col

        df = df.rename(columns=cleaned_columns)

        table_base = display_name if display_name.strip() else Path(filename).stem
        table_name = clean_identifier(table_base)

        success, nchunks, nrows, _ = write_pandas(
            conn=connection,
            df=df,
            table_name=table_name,
            database="DATAMIND_DB",
            schema="PUBLIC",
            auto_create_table=True,
            overwrite=True,
        )

        if not success:
            return False, f"Failed to upload data to Snowflake table {table_name}.", None

        columns_meta: dict[str, dict[str, str]] = {}
        for col in df.columns:
            col_type = infer_column_type(df[col].dtype)
            columns_meta[col] = {
                "type": col_type,
                "description": f"{col} ({col_type.lower()} value)",
            }

        dataset_id = table_name.lower()
        config_data = {
            "dataset": dataset_id,
            "display_name": display_name.strip() or table_name.title().replace("_", " "),
            "description": f"Uploaded dataset '{display_name}' containing {nrows:,} rows and {len(df.columns)} columns.",
            "snowflake": {
                "database": "DATAMIND_DB",
                "schema": "PUBLIC",
            },
            "tables": {
                table_name: {
                    "description": f"Uploaded table containing {', '.join(list(df.columns)[:8])}.",
                    "columns": columns_meta,
                }
            },
            "joins": [],
            "synonyms": {},
            "metrics": {},
            "examples": [
                {
                    "q": f"Show the first 5 rows of {table_name}",
                    "sql": f"SELECT * FROM DATAMIND_DB.PUBLIC.{table_name} LIMIT 5",
                }
            ],
            "limits": {"max_rows": 1000},
            "guardrails": {
                "max_rows": 1000,
                "allowed_tables": [table_name],
                "blocked_columns": [],
            },
        }

        config_path = os.path.join(configs_dir, f"{dataset_id}.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, sort_keys=False, default_flow_style=False)

        return (
            True,
            f"Successfully uploaded {nrows:,} rows to {table_name} and created dataset config.",
            config_path,
        )

    except Exception as exc:
        return False, f"Error processing upload: {exc}", None
