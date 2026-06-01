#!/usr/bin/env python3

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

    return events


def chunked(items: list[dict[str, Any]], batch_size: int):
    for index in range(0, len(items), batch_size):
        yield items[index:index + batch_size]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay generated CCTV events into the API in simulated real time."
    )
    parser.add_argument("--file", required=True, help="Path to generated JSONL event file.")
    parser.add_argument("--url", default="http://localhost:8000/events/ingest")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    args = parser.parse_args()

    path = Path(args.file)

    if not path.exists():
        raise FileNotFoundError(f"Event file not found: {path}")

    events = read_jsonl(path)

    print(f"Loaded {len(events)} events from {path}")
    print(f"Posting to {args.url}")
    print(f"Batch size: {args.batch_size}, delay: {args.delay_seconds}s")

    accepted_total = 0
    duplicate_total = 0
    invalid_total = 0

    for batch_number, batch in enumerate(chunked(events, args.batch_size), start=1):
        response = requests.post(args.url, json={"events": batch}, timeout=30)
        response.raise_for_status()
        payload = response.json()

        accepted = payload.get("accepted_count", 0)
        duplicates = payload.get("duplicate_count", 0)
        invalid = payload.get("invalid_count", 0)

        accepted_total += accepted
        duplicate_total += duplicates
        invalid_total += invalid

        print(
            f"batch={batch_number} "
            f"sent={len(batch)} "
            f"accepted={accepted} "
            f"duplicates={duplicates} "
            f"invalid={invalid}"
        )

        time.sleep(args.delay_seconds)

    print("Replay complete")
    print(
        json.dumps(
            {
                "accepted_total": accepted_total,
                "duplicate_total": duplicate_total,
                "invalid_total": invalid_total,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
