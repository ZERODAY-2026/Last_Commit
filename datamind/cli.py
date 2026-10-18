import argparse
import json
import os

from .config import DatasetConfig
from .gemma_client import OllamaGemma
from .orchestrator import DataMind
from .snowflake_client import SnowflakeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask Snowflake questions with local Gemma.")
    parser.add_argument("question")
    parser.add_argument("--config", default=os.getenv("DATASET_CONFIG", "configs/tpch.yaml"))
    args = parser.parse_args()
    agent = DataMind(DatasetConfig.from_file(args.config), OllamaGemma(), SnowflakeClient())
    print(json.dumps(agent.answer(args.question).__dict__, indent=2, default=str))


if __name__ == "__main__":
    main()
