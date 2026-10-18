import pytest

from datamind.validator import ValidationError, validate_sql


ALLOWED = {"SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS"}


def test_select_is_allowed_and_gets_limit():
    result = validate_sql("SELECT O_ORDERDATE FROM ORDERS", ALLOWED, 100)
    assert "LIMIT 100" in result.sql.upper()


@pytest.mark.parametrize(
    "sql",
    ["DELETE FROM ORDERS", "SELECT 1; SELECT 2", "SELECT * FROM OTHER_TABLE", "SELECT * FROM ORDERS -- bypass"],
)
def test_unsafe_sql_is_rejected(sql):
    with pytest.raises(ValidationError):
        validate_sql(sql, ALLOWED, 100)
