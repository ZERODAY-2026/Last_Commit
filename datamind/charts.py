from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px


def result_chart(rows: list[dict[str, Any]]):
    """Return a chart only when the verified result has a useful shape."""
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    if len(frame.columns) != 2:
        return None
    category, measure = frame.columns
    if pd.api.types.is_numeric_dtype(frame[measure]):
        return px.bar(frame, x=category, y=measure, color_discrete_sequence=["#0E6B72"])
    return None
