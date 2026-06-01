#!/usr/bin/env python3

import argparse
import csv
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


POS_MATCH_WINDOW_MINUTES = 5


def parse_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            events.append(json.loads(line))

    return events


def read_pos_transactions(path: Path) -> list[dict[str, Any]]:
    transactions: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            timestamp_value = (
                row.get("timestamp_utc")
                or row.get("timestamp")
                or row.get("transaction_timestamp")
            )

            if not timestamp_value:
                continue

            transactions.append(
                {
                    "store_id": row["store_id"],
                    "transaction_id": row["transaction_id"],
                    "timestamp": parse_datetime(timestamp_value),
                }
            )

    return transactions


def select_converted_billing_events(
    billing_events: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
) -> set[str]:
    converted_event_ids: set[str] = set()
    converted_visitor_ids: set[str] = set()

    billing_with_time = [
        {
            "event": event,
            "timestamp": parse_datetime(event["timestamp"]),
        }
        for event in billing_events
    ]

    for transaction in sorted(
        transactions,
        key=lambda item: parse_datetime(item["timestamp"]) if isinstance(item["timestamp"], str) else item["timestamp"],
    ):
        transaction_time = (
            parse_datetime(transaction["timestamp"])
            if isinstance(transaction["timestamp"], str)
            else transaction["timestamp"]
        )
        window_start = transaction_time - timedelta(minutes=POS_MATCH_WINDOW_MINUTES)

        candidates = []

        for item in billing_with_time:
            event = item["event"]
            event_time = item["timestamp"]

            if event["store_id"] != transaction["store_id"]:
                continue

            if event["visitor_id"] in converted_visitor_ids:
                continue

            if window_start <= event_time <= transaction_time:
                candidates.append(item)

        if not candidates:
            continue

        selected = max(candidates, key=lambda item: item["timestamp"])
        selected_event = selected["event"]

        converted_event_ids.add(selected_event["event_id"])
        converted_visitor_ids.add(selected_event["visitor_id"])

    return converted_event_ids


def build_abandon_events(
    events: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    billing_events = [
        event
        for event in events
        if event.get("event_type") == "BILLING_QUEUE_JOIN"
        and not event.get("is_staff", False)
    ]

    converted_billing_event_ids = select_converted_billing_events(
        billing_events=billing_events,
        transactions=transactions,
    )

    existing_abandon_visitors = {
        event.get("visitor_id")
        for event in events
        if event.get("event_type") == "BILLING_QUEUE_ABANDON"
    }

    latest_billing_event_by_visitor: dict[str, dict[str, Any]] = {}

    for event in billing_events:
        visitor_id = event["visitor_id"]
        current_time = parse_datetime(event["timestamp"])

        previous = latest_billing_event_by_visitor.get(visitor_id)

        if previous is None:
            latest_billing_event_by_visitor[visitor_id] = event
            continue

        previous_time = parse_datetime(previous["timestamp"])

        if current_time > previous_time:
            latest_billing_event_by_visitor[visitor_id] = event

    abandon_events: list[dict[str, Any]] = []

    converted_visitors = {
        event["visitor_id"]
        for event in billing_events
        if event["event_id"] in converted_billing_event_ids
    }

    for visitor_id, billing_event in latest_billing_event_by_visitor.items():
        if visitor_id in converted_visitors:
            continue

        if visitor_id in existing_abandon_visitors:
            continue

        billing_time = parse_datetime(billing_event["timestamp"])
        abandon_time = billing_time + timedelta(minutes=POS_MATCH_WINDOW_MINUTES)

        metadata = dict(billing_event.get("metadata") or {})
        metadata.update(
            {
                "source_event_id": billing_event["event_id"],
                "correlation_window_minutes": POS_MATCH_WINDOW_MINUTES,
                "reason": "no_pos_transaction_matched_after_billing_join",
            }
        )

        abandon_events.append(
            {
                "event_id": str(uuid.uuid4()),
                "store_id": billing_event["store_id"],
                "camera_id": billing_event["camera_id"],
                "visitor_id": visitor_id,
                "event_type": "BILLING_QUEUE_ABANDON",
                "timestamp": format_datetime(abandon_time),
                "zone_id": billing_event.get("zone_id") or "ZONE_BILLING_QUEUE",
                "dwell_ms": 0,
                "is_staff": False,
                "confidence": billing_event.get("confidence", 0.0),
                "metadata": metadata,
            }
        )

    return abandon_events


def write_events(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    sorted_events = sorted(events, key=lambda event: event["timestamp"])

    with path.open("w", encoding="utf-8") as file:
        for event in sorted_events:
            file.write(json.dumps(event) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append BILLING_QUEUE_ABANDON events using POS correlation."
    )
    parser.add_argument("--events", required=True, help="Input generated events JSONL.")
    parser.add_argument("--pos", required=True, help="Normalized POS transactions CSV.")
    parser.add_argument("--output", required=True, help="Output JSONL with abandonment events.")
    args = parser.parse_args()

    events_path = Path(args.events)
    pos_path = Path(args.pos)
    output_path = Path(args.output)

    if not events_path.exists():
        raise FileNotFoundError(f"Events file not found: {events_path}")

    if not pos_path.exists():
        raise FileNotFoundError(f"POS file not found: {pos_path}")

    events = read_events(events_path)
    transactions = read_pos_transactions(pos_path)
    abandon_events = build_abandon_events(events, transactions)

    output_events = events + abandon_events
    write_events(output_path, output_events)

    print(
        json.dumps(
            {
                "input_event_count": len(events),
                "transaction_count": len(transactions),
                "abandon_event_count": len(abandon_events),
                "output_event_count": len(output_events),
                "output": str(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
