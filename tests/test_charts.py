from datamind.charts import result_chart


def test_chart_returns_none_on_empty():
    assert result_chart([]) is None


def test_chart_generates_bar_for_category_and_numeric():
    rows = [
        {"NATION": "FRANCE", "REVENUE": 100},
        {"NATION": "GERMANY", "REVENUE": 150},
    ]
    fig = result_chart(rows)
    assert fig is not None


def test_chart_generates_line_for_year_and_numeric():
    rows = [
        {"YEAR": 1995, "ORDERS": 200},
        {"YEAR": 1996, "ORDERS": 300},
    ]
    fig = result_chart(rows)
    assert fig is not None


def test_chart_handles_snowflake_decimal_types():
    from decimal import Decimal

    rows = [
        {"ENTITY": "India", "PRIMARY": Decimal("79140000.0000000")},
        {"ENTITY": "China", "PRIMARY": Decimal("48840000.0000000")},
    ]
    fig = result_chart(rows)
    assert fig is not None


def test_chart_handles_entity_year_metric():
    from decimal import Decimal

    rows = [
        {"ENTITY": "India", "YEAR": 2010, "PRIMARY": Decimal("5000")},
        {"ENTITY": "India", "YEAR": 2011, "PRIMARY": Decimal("5500")},
    ]
    fig = result_chart(rows)
    assert fig is not None
