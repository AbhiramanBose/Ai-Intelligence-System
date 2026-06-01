#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import requests


def load_jsonl(path: Path) -> list[dict]:
    events = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay generated JSONL events into the API.")
    parser.add_argument("--file", default="data/fixtures/valid_events.jsonl")
    parser.add_argument("--url", default="http://localhost:8000/events/ingest")
    args = parser.parse_args()

    health_url = args.url.replace("/events/ingest", "/health")

    try:
        health_response = requests.get(health_url, timeout=5)
        health_response.raise_for_status()
    except requests.exceptions.RequestException:
        print("API is not running.")
        print(f"Start the API first, then verify: curl {health_url}")
        print("Docker command: docker compose up --build")
        return

    events = load_jsonl(Path(args.file))

    response = requests.post(args.url, json={"events": events}, timeout=30)
    print(response.status_code)

    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)


if __name__ == "__main__":
    main()