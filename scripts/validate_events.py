#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from pydantic import ValidationError
from app.schemas.event_schema import EventIn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/fixtures/valid_events.jsonl")
    args = parser.parse_args()
    path = Path(args.file)
    valid = invalid = 0
    for i, line in enumerate(path.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            EventIn.model_validate(json.loads(line))
            valid += 1
        except (ValidationError, json.JSONDecodeError) as exc:
            print(f"Invalid line {i + 1}: {exc}")
            invalid += 1
    print({"valid": valid, "invalid": invalid})


if __name__ == "__main__":
    main()
