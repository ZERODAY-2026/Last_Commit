from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px


def result_chart(rows: list[dict[str, Any]]):
    """Return an interactive chart built strictly from verified result rows."""
    if not rows or len(rows) < 2:
        return None
    frame = pd.DataFrame(rows)
    cols = list(frame.columns)
    if len(cols) == 2:
        col1, col2 = cols
        # Check which column is numeric
        num_col = col2 if pd.api.types.is_numeric_dtype(frame[col2]) else (col1 if pd.api.types.is_numeric_dtype(frame[col1]) else None)
        cat_col = col1 if num_col == col2 else col2
        if num_col and cat_col:
            # If cat_col represents time/years/dates, use a line chart
            is_time = (
                pd.api.types.is_datetime64_any_dtype(frame[cat_col])
                or any(t in str(cat_col).upper() for t in ("YEAR", "DATE", "MONTH", "DAY", "TIME"))
            )
            if is_time:
                fig = px.line(
                    frame.sort_values(cat_col),
                    x=cat_col,
                    y=num_col,
                    markers=True,
                    color_discrete_sequence=["#0E6B72"],
                    template="plotly_white",
                )
            else:
                fig = px.bar(
                    frame,
                    x=cat_col,
                    y=num_col,
                    color_discrete_sequence=["#0E6B72"],
                    template="plotly_white",
                )
            fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=380)
            return fig
    elif len(cols) >= 3:
        # Check if we have 2 categorical/time and 1 numeric
        num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(frame[c])]
        cat_cols = [c for c in cols if c not in num_cols]
        if len(num_cols) == 1 and len(cat_cols) >= 2:
            x_col = cat_cols[0]
            color_col = cat_cols[1]
            y_col = num_cols[0]
            fig = px.bar(
                frame,
                x=x_col,
                y=y_col,
                color=color_col,
                barmode="group",
                template="plotly_white",
            )
            fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=380)
            return fig
    return None
