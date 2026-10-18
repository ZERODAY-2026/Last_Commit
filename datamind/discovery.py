from __future__ import annotations

import os
from typing import Any
import yaml


def discover_and_profile_schema(
    connection: Any,
    database: str,
    schema: str,
    sample_rows: int = 10000,
    output_dir: str = "configs",
) -> tuple[dict[str, Any], str]:
    """Query Snowflake INFORMATION_SCHEMA, profile columns, and write <dataset>.generated.yaml."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM {database}.INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{schema.upper()}'
            ORDER BY TABLE_NAME, ORDINAL_POSITION"""
        )
        rows = cursor.fetchall()
        tables: dict[str, Any] = {}
        for table_name, col_name, data_type, is_null in rows:
            tbl = str(table_name).upper()
            col = str(col_name).upper()
            dtype = str(data_type).upper()
            if tbl not in tables:
                tables[tbl] = {
                    "description": f"Table {tbl} discovered from {database}.{schema}",
                    "columns": {},
                    "generated": True,
                }
            # Map Snowflake types to DataMind types
            mapped_type = "NUMBER" if any(k in dtype for k in ("INT", "FLOAT", "NUMBER", "DECIMAL")) else ("DATE" if any(k in dtype for k in ("DATE", "TIME")) else "TEXT")
            tables[tbl]["columns"][col] = {
                "type": mapped_type,
                "description": f"{col} column ({dtype.lower()})",
                "nullable": is_null == "YES",
            }

        dataset_id = f"{database}_{schema}".lower()
        config_dict = {
            "dataset": dataset_id,
            "display_name": f"{database}.{schema} (Discovered)",
            "description": f"Auto-discovered schema from {database}.{schema} with {len(tables)} tables.",
            "generated": True,
            "snowflake": {
                "database": database.upper(),
                "schema": schema.upper(),
            },
            "tables": tables,
            "joins": [],
            "synonyms": {},
            "metrics": {},
            "examples": [],
            "limits": {"max_rows": 1000},
            "guardrails": {
                "max_rows": 1000,
                "allowed_tables": list(tables.keys()),
                "blocked_columns": [],
            },
        }

        output_path = os.path.join(output_dir, f"{dataset_id}.generated.yaml")
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, sort_keys=False, default_flow_style=False)

        return config_dict, output_path
    finally:
        cursor.close()
