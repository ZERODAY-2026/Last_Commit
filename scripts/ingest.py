#!/usr/bin/env python3
"""CLI utility to ingest files (CSV, Excel) into Snowflake and auto-generate DataMind YAML configs.
Feature #10, #11 from DataMind Advanced Features Implementation Guide.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from datamind.snowflake_client import SnowflakeClient
from datamind.uploader import upload_file_to_snowflake


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Ingest a file into Snowflake and generate DataMind config")
    parser.add_argument("--source", required=True, help="Path to CSV or Excel file")
    parser.add_argument("--table", default="", help="Optional Snowflake table name")
    parser.add_argument("--name", default="", help="Display name for the dataset")
    args = parser.parse_args()

    file_path = Path(args.source)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 1

    print(f"Connecting to Snowflake and ingesting {file_path.name}...")
    sf = SnowflakeClient()
    conn = sf._connect()

    with open(file_path, "rb") as f:
        f.name = file_path.name
        success, msg, cfg = upload_file_to_snowflake(
            f, display_name=args.name or args.table or file_path.stem, connection=conn
        )

    if success:
        print(f"Success: {msg}")
        print(f"Generated configuration: {cfg}")
        return 0
    else:
        print(f"Failed: {msg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
