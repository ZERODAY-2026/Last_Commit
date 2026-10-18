from datamind.quality import compute_data_quality, estimate_query_cost


def test_data_quality_computes_completeness_and_stats():
    rows = [
        {"ID": 1, "NAME": "Alice", "SCORE": 95.0},
        {"ID": 2, "NAME": None, "SCORE": 80.0},
    ]
    dq = compute_data_quality(rows)
    assert dq["row_count"] == 2
    assert dq["null_cells"] == 1
    assert dq["completeness_pct"] < 100.0
    assert "SCORE" in dq["columns"]
    assert dq["columns"]["SCORE"]["min"] == 80.0
    assert dq["columns"]["SCORE"]["max"] == 95.0


def test_estimate_query_cost():
    cost = estimate_query_cost(1500, warehouse_size="XSMALL")
    assert cost["runtime_ms"] == 1500
    assert cost["estimated_credits"] > 0
