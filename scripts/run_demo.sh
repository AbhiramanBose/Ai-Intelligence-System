#!/usr/bin/env bash
set -euo pipefail
python scripts/seed_store_layout.py || true
python scripts/seed_pos_transactions.py || true
python scripts/replay_events.py --file data/fixtures/valid_events.jsonl
curl -s http://localhost:8000/stores/ST1008/metrics | python -m json.tool
