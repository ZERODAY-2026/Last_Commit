from __future__ import annotations

from typing import Any
import pandas as pd


def compute_data_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute data-quality metrics and column profiling on query results."""
    if not rows:
        return {"row_count": 0, "completeness_pct": 100.0, "columns": {}}

    df = pd.DataFrame(rows)
    total_cells = df.size
    null_cells = int(df.isna().sum().sum())
    completeness = round(((total_cells - null_cells) / total_cells) * 100, 1) if total_cells > 0 else 100.0

    col_profiles: dict[str, dict[str, Any]] = {}
    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        distinct_count = int(series.nunique(dropna=True))
        profile: dict[str, Any] = {
            "type": str(series.dtype),
            "nulls": null_count,
            "distinct": distinct_count,
        }
        if pd.api.types.is_numeric_dtype(series) and not series.dropna().empty:
            profile["min"] = float(series.min())
            profile["max"] = float(series.max())
            profile["avg"] = round(float(series.mean()), 2)
        col_profiles[str(col)] = profile

    return {
        "row_count": len(df),
        "total_columns": len(df.columns),
        "null_cells": null_cells,
        "completeness_pct": completeness,
        "columns": col_profiles,
    }


def estimate_query_cost(runtime_ms: int, warehouse_size: str = "XSMALL") -> dict[str, Any]:
    """Estimate Snowflake credit usage and reliability status based on runtime."""
    # Snowflake credits per hour by size
    size_credits = {
        "XSMALL": 1.0,
        "SMALL": 2.0,
        "MEDIUM": 4.0,
        "LARGE": 8.0,
        "XLARGE": 16.0,
    }
    credits_per_hour = size_credits.get(warehouse_size.upper(), 1.0)
    seconds = max(runtime_ms / 1000.0, 0.05)
    estimated_credits = round(seconds * (credits_per_hour / 3600.0), 6)

    return {
        "warehouse_size": warehouse_size,
        "runtime_ms": runtime_ms,
        "runtime_seconds": round(seconds, 3),
        "estimated_credits": estimated_credits,
        "auto_suspend_seconds": 60,
    }
