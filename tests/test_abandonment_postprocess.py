# PROMPT:
# Generate pytest tests for post-processing billing queue abandonment events from generated CCTV events and POS transactions.
# A billing visitor with no POS transaction in the five-minute window should receive a BILLING_QUEUE_ABANDON event.
#
# CHANGES MADE:
# Used temporary JSONL and CSV files so the test does not depend on the challenge dataset or local processed files.

import csv
import json
from pathlib import Path
from uuid import uuid4

from scripts.postprocess_abandonment_events import (
    build_abandon_events,
    read_events,
    read_pos_transactions,
    write_events,
)


def make_billing_event(store_id: str, visitor_id: str, timestamp: str) -> dict:
    return {
        "event_id": str(uuid4()),
        "store_id": store_id,
        "camera_id": "CAM_BILLING_TEST",
        "visitor_id": visitor_id,
        "event_type": "BILLING_QUEUE_JOIN",
        "timestamp": timestamp,
        "zone_id": "ZONE_BILLING_QUEUE",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.9,
        "metadata": {
            "queue_depth": 1,
            "session_seq": 1,
        },
    }


def test_postprocess_emits_abandon_for_unmatched_billing_visitor(tmp_path: Path):
    store_id = "ABANDON_TEST_STORE"

    events = [
        make_billing_event(store_id, "VIS_UNMATCHED", "2026-04-10T14:00:00Z"),
    ]

    transactions = [
        {
            "store_id": store_id,
            "transaction_id": "TXN_TOO_LATE",
            "timestamp": "2026-04-10T14:10:00Z",
        }
    ]

    abandon_events = build_abandon_events(events, transactions)

    assert len(abandon_events) == 1

    abandon_event = abandon_events[0]

    assert abandon_event["event_type"] == "BILLING_QUEUE_ABANDON"
    assert abandon_event["store_id"] == store_id
    assert abandon_event["visitor_id"] == "VIS_UNMATCHED"
    assert abandon_event["zone_id"] == "ZONE_BILLING_QUEUE"
    assert abandon_event["metadata"]["correlation_window_minutes"] == 5


def test_postprocess_does_not_emit_abandon_for_matched_billing_visitor():
    store_id = "ABANDON_TEST_STORE"

    events = [
        make_billing_event(store_id, "VIS_MATCHED", "2026-04-10T14:00:00Z"),
    ]

    transactions = [
        {
            "store_id": store_id,
            "transaction_id": "TXN_MATCHED",
            "timestamp": "2026-04-10T14:04:00Z",
        }
    ]

    abandon_events = build_abandon_events(events, transactions)

    assert abandon_events == []


def test_postprocess_read_write_roundtrip(tmp_path: Path):
    events_path = tmp_path / "events.jsonl"
    pos_path = tmp_path / "pos.csv"
    output_path = tmp_path / "output.jsonl"

    event = make_billing_event("ROUNDTRIP_STORE", "VIS_ROUNDTRIP", "2026-04-10T14:00:00Z")

    events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pos_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["store_id", "transaction_id", "timestamp_utc"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "store_id": "ROUNDTRIP_STORE",
                "transaction_id": "TXN_TOO_LATE",
                "timestamp_utc": "2026-04-10T14:10:00Z",
            }
        )

    events = read_events(events_path)
    transactions = read_pos_transactions(pos_path)
    abandon_events = build_abandon_events(events, transactions)

    write_events(output_path, events + abandon_events)

    output_lines = output_path.read_text(encoding="utf-8").strip().splitlines()

    assert len(output_lines) == 2

    output_events = [json.loads(line) for line in output_lines]

    assert {event["event_type"] for event in output_events} == {
        "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON",
    }
