# Adding a dataset

1. Load a licensed dataset into Snowflake.
2. Add a YAML file under `configs/` with `dataset`, database/schema, table and
   column descriptions, joins, metrics, synonyms, examples, and guardrails.
3. Set `DATASET_CONFIG` to that file.
4. Run the unit tests and the golden questions against the new dataset.

No dataset-specific Python code should be needed. Do not commit copied
Snowflake sample data or data whose licence does not allow redistribution.
