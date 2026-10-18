#!/usr/bin/env python3
"""CLI utility to discover tables from Snowflake INFORMATION_SCHEMA and generate YAML configs.
Feature #5 from DataMind Advanced Features Implementation Guide.
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
from datamind.discovery import discover_and_profile_schema
from datamind.snowflake_client import SnowflakeClient


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Discover Snowflake schema and generate DataMind config")
    parser.add_argument("--database", default="DATAMIND_DB", help="Snowflake database")
    parser.add_argument("--schema", default="PUBLIC", help="Snowflake schema")
    parser.add_argument("--out", default="configs", help="Output configs directory")
    args = parser.parse_args()

    print(f"Connecting to Snowflake and inspecting {args.database}.{args.schema}...")
    sf = SnowflakeClient()
    conn = sf._connect()

    try:
        config, out_path = discover_and_profile_schema(
            conn, database=args.database, schema=args.schema, output_dir=args.out
        )
        print(f"Success! Discovered {len(config['tables'])} table(s).")
        print(f"Generated configuration written to: {out_path}")
        return 0
    except Exception as exc:
        print(f"Discovery error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
