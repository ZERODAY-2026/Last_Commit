from datamind.config import DatasetConfig


def test_tpch_config_builds_schema_prompt():
    config = DatasetConfig.from_file("configs/tpch.yaml")
    prompt = config.prompt_schema()
    assert "ORDERS" in prompt
    assert "O_ORDERDATE" in prompt
    assert config.max_rows == 1000
