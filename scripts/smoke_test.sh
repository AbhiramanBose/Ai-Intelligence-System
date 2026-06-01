#!/usr/bin/env bash
set -euo pipefail

curl -s http://localhost:8000/health | python -m json.tool
python scripts/replay_events.py --file data/fixtures/valid_events.jsonl
curl -s http://localhost:8000/stores/ST1008/metrics | python -m json.tool
curl -s http://localhost:8000/stores/ST1008/funnel | python -m json.tool
curl -s http://localhost:8000/stores/ST1008/heatmap | python -m json.tool
curl -s http://localhost:8000/stores/ST1008/anomalies | python -m json.tool
