from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px


def result_chart(rows: list[dict[str, Any]]):
    """Return an interactive chart built strictly from verified result rows."""
    if not rows or len(rows) < 2:
        return None
    frame = pd.DataFrame(rows)
    for col in frame.columns:
        try:
            frame[col] = pd.to_numeric(frame[col])
        except (ValueError, TypeError):
            pass

    cols = list(frame.columns)
    time_names = ("YEAR", "DATE", "MONTH", "DAY", "TIME", "PERIOD")
    time_cols = [
        c
        for c in cols
        if any(t in str(c).upper() for t in time_names)
        or pd.api.types.is_datetime64_any_dtype(frame[c])
    ]
    metric_cols = [
        c for c in cols if pd.api.types.is_numeric_dtype(frame[c]) and c not in time_cols
    ]
    dim_cols = [c for c in cols if c not in metric_cols and c not in time_cols]

    # If no separate metric, but we have multiple numeric time_cols, treat the last as metric
    if not metric_cols and len(time_cols) > 1:
        metric_cols.append(time_cols.pop())

    if not metric_cols:
        return None

    metric = metric_cols[0]

    # Time series (with or without category)
    if time_cols:
        t_col = time_cols[0]
        sorted_frame = frame.sort_values(t_col)
        if dim_cols:
            fig = px.line(
                sorted_frame,
                x=t_col,
                y=metric,
                color=dim_cols[0],
                markers=True,
                template="plotly_white",
            )
        else:
            fig = px.line(
                sorted_frame,
                x=t_col,
                y=metric,
                markers=True,
                color_discrete_sequence=["#0E6B72"],
                template="plotly_white",
            )
        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=380)
        return fig

    # Categorical bar chart
    if dim_cols:
        d_col = dim_cols[0]
        if len(dim_cols) >= 2:
            fig = px.bar(
                frame,
                x=d_col,
                y=metric,
                color=dim_cols[1],
                barmode="group",
                template="plotly_white",
            )
        else:
            fig = px.bar(
                frame,
                x=d_col,
                y=metric,
                color_discrete_sequence=["#0E6B72"],
                template="plotly_white",
            )
        fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=380)
        return fig

    return None
