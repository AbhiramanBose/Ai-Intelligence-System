# Runbook

This runbook explains how to run the Store Intelligence System from a clean local state.

It covers:

```text
environment setup
database reset
POS seeding
CCTV pipeline execution
event replay
API verification
test and coverage validation
Docker validation
Git hygiene
```

---

## 1. Activate virtual environment

From the project root:

```bash
cd "/Users/anuranjanbose/Desktop/Purplle tech/store-intelligence-starter"
source .venv/bin/activate
```

Verify Python path:

```bash
which python
```

Expected:

```text
/Users/anuranjanbose/Desktop/Purplle tech/store-intelligence-starter/.venv/bin/python
```

---

## 2. Install dependencies

If running for the first time:

```bash
pip install -r requirements.txt
```

---

## 3. Confirm raw dataset placement

Raw challenge data must be placed locally but must not be committed to Git.

Expected Store 1 files:

```text
data/raw/stores/store_1/CAM 1 - zone.mp4
data/raw/stores/store_1/CAM 2 - zone.mp4
data/raw/stores/store_1/CAM 3 - entry.mp4
data/raw/stores/store_1/CAM 5 - billing.mp4
data/raw/stores/store_1/layout.png
```

Expected Store 2 files:

```text
data/raw/stores/store_2/entry 1.mp4
data/raw/stores/store_2/entry 2.mp4
data/raw/stores/store_2/zone.mp4
data/raw/stores/store_2/billing_area.mp4
data/raw/stores/store_2/layout.png
```

Expected POS file:

```text
data/raw/pos/pos_transactions.csv
```

Check files:

```bash
ls "data/raw/stores/store_1"
ls "data/raw/stores/store_2"
ls "data/raw/pos"
```

---

## 4. Validate store configs

```bash
python -m json.tool configs/stores/store_1.json > /tmp/store_1_check.json
python -m json.tool configs/stores/store_2.json > /tmp/store_2_check.json
```

No output means the JSON is valid.

Store config summary:

```text
Store 1 config: configs/stores/store_1.json
Store 1 store_id: ST1008

Store 2 config: configs/stores/store_2.json
Store 2 store_id: ST1076
```

---

## 5. Reset local database

Stop the API server if it is running, then reset SQLite:

```bash
rm -f storage/store_intelligence.db
```

This removes old test/demo records so the final run contains only the two real stores.

---

## 6. Seed POS transactions

Run:

```bash
python scripts/seed_pos_transactions.py
```

Expected output:

```text
Input POS file: data/raw/pos/pos_transactions.csv
Raw POS rows: 101
Normalized POS transactions: 24
Inserted: 24
Skipped duplicates: 0
Output: data/processed/normalized_pos_transactions.csv
```

The POS CSV is item-level. The script normalizes 101 product-line rows into 24 transaction-level POS records.

---

## 7. Run Store 1 CCTV pipeline

```bash
python pipeline/run_pipeline.py \
  --store-config configs/stores/store_1.json \
  --output data/processed/store_1/generated_events.jsonl
```

Expected summary:

```text
store_id: ST1008
event_count: 371
cameras_processed: CAM_1, CAM_2, CAM_3, CAM_5
suppressed_entry_overlap_count: 0
```

Store 1 has one entry camera, so entry-overlap suppression is not required.

---

## 8. Run Store 2 CCTV pipeline

```bash
python pipeline/run_pipeline.py \
  --store-config configs/stores/store_2.json \
  --output data/processed/store_2/generated_events.jsonl
```

Expected summary:

```text
store_id: ST1076
event_count: 138
cameras_processed: ENTRY_1, ENTRY_2, ZONE, BILLING
suppressed_entry_overlap_count: 25
```

Store 2 has two entry cameras. `ENTRY_2` is the configured entry source of truth, and duplicate session events from `ENTRY_1` are suppressed.

---

## 9. Start API server

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Keep this terminal running.

---

## 10. Replay generated events

Open another terminal, activate the environment again, and run:

```bash
source .venv/bin/activate
```

Replay Store 1:

```bash
python scripts/replay_events.py --file data/processed/store_1/generated_events.jsonl
```

Expected:

```text
accepted_count: 371
duplicate_count: 0
invalid_count: 0
```

Replay Store 2:

```bash
python scripts/replay_events.py --file data/processed/store_2/generated_events.jsonl
```

Expected:

```text
accepted_count: 138
duplicate_count: 0
invalid_count: 0
```

---

## 11. Verify health endpoint

```bash
curl http://localhost:8000/health
```

Expected shape:

```json
{
  "status": "degraded",
  "database": "connected",
  "last_event_timestamp_by_store": {
    "ST1008": "2026-04-10T14:41:19",
    "ST1076": "2026-04-10T14:40:54"
  },
  "warnings": [
    {
      "type": "STALE_FEED",
      "store_id": "ST1008"
    },
    {
      "type": "STALE_FEED",
      "store_id": "ST1076"
    }
  ]
}
```

`status: degraded` is expected for offline replay because the event timestamps come from historical CCTV clips.

Important: only `ST1008` and `ST1076` should appear after a clean DB reset.

---

## 12. Verify metrics

ST1008:

```bash
curl http://localhost:8000/stores/ST1008/metrics
```

Expected:

```json
{
  "store_id": "ST1008",
  "unique_visitors": 4,
  "conversion_rate": 0.0,
  "avg_dwell_per_zone": {
    "ZONE_FOH": 62850.55,
    "ZONE_BILLING_QUEUE": 30622.5
  },
  "current_queue_depth": 2,
  "abandonment_rate": 1.0
}
```

ST1076:

```bash
curl http://localhost:8000/stores/ST1076/metrics
```

Expected:

```json
{
  "store_id": "ST1076",
  "unique_visitors": 31,
  "conversion_rate": 0.0,
  "avg_dwell_per_zone": {
    "ZONE_BILLING_QUEUE": 30000.0
  },
  "current_queue_depth": 2,
  "abandonment_rate": 0.0
}
```

---

## 13. Verify funnel

ST1008:

```bash
curl http://localhost:8000/stores/ST1008/funnel
```

Expected:

```text
ENTRY: 4
PRODUCT_ZONE_VISIT: 4
BILLING_QUEUE: 4
PURCHASE: 0
```

ST1076:

```bash
curl http://localhost:8000/stores/ST1076/funnel
```

Expected:

```text
ENTRY: 31
PRODUCT_ZONE_VISIT: 10
BILLING_QUEUE: 10
PURCHASE: 0
```

---

## 14. Verify conversion debug

ST1008:

```bash
curl http://localhost:8000/stores/ST1008/conversion-debug
```

Expected key values:

```text
entry_count: 4
billing_count: 4
converted_count: 0
abandoned_count: 4
transaction_count: 24
matched_transaction_count: 0
unmatched_transaction_count: 24
conversion_source: pos_correlation
abandonment_source: unmatched_billing_visitors
```

ST1076:

```bash
curl http://localhost:8000/stores/ST1076/conversion-debug
```

Expected key values:

```text
entry_count: 31
billing_count: 10
converted_count: 0
transaction_count: 0
conversion_source: no_pos_transactions_loaded
```

ST1076 has no POS transactions in the supplied POS CSV, so the system reports this transparently.

---

## 15. Verify heatmap

```bash
curl http://localhost:8000/stores/ST1008/heatmap
curl http://localhost:8000/stores/ST1076/heatmap
```

Expected:

```text
JSON response with zones, visit_count, avg_dwell_ms, heat_score, and data_confidence
```

---

## 16. Verify anomalies

```bash
curl http://localhost:8000/stores/ST1008/anomalies
curl http://localhost:8000/stores/ST1076/anomalies
```

Expected possible results:

```text
STALE_FEED
CONVERSION_BASELINE_UNAVAILABLE
```

Conversion baseline unavailable is expected because the supplied challenge data is single-day and does not include a seven-day historical baseline.

---

## 17. Run tests

```bash
python -m pytest
```

Expected:

```text
24 passed
```

---

## 18. Run coverage

```bash
python -m pytest --cov=app --cov=pipeline --cov-config=.coveragerc
```

Expected:

```text
TOTAL coverage: 86%
```

Do not include `--cov=scripts` in the final coverage command unless script tests are added, because utility scripts are mostly operational entry points.

---

## 19. Docker validation

Stop local Uvicorn first.

Then run:

```bash
docker compose down -v
docker compose up --build
```

In another terminal:

```bash
curl http://localhost:8000/health
```

Expected:

```text
API responds
database connected
status may be degraded because offline replay timestamps are historical
```

---

## 20. Git hygiene check

Raw and generated data must not be committed.

Run:

```bash
git status --short data/raw
git status --short data/processed
```

Expected:

```text
no output
```

Check full status:

```bash
git status --short
```

Do not commit:

```text
data/raw/
data/processed/
storage/*.db
*.mp4
*.mov
*.avi
*.mkv
yolov8n.pt
README.backup.md
```

Remove README backup before final commit:

```bash
rm -f README.backup.md
```

---

## 21. Final validation checklist

Before final submission, confirm:

```text
[ ] python -m pytest passes
[ ] coverage is above 70%
[ ] Store 1 pipeline produces 371 events
[ ] Store 2 pipeline produces 138 events
[ ] Store 2 suppresses 25 entry-overlap events
[ ] POS seeding normalizes 101 rows into 24 transactions
[ ] ST1008 metrics endpoint works
[ ] ST1076 metrics endpoint works
[ ] conversion-debug works for both stores
[ ] /health shows only ST1008 and ST1076 after DB reset
[ ] raw CCTV files are not tracked by Git
[ ] generated JSONL files are not tracked by Git
[ ] README, DESIGN, CHOICES, METRIC_DEFINITIONS, RUNBOOK are updated
```

---

## 22. Clean final command sequence

Use this sequence for final demo verification:

```bash
rm -f storage/store_intelligence.db

python scripts/seed_pos_transactions.py

python pipeline/run_pipeline.py \
  --store-config configs/stores/store_1.json \
  --output data/processed/store_1/generated_events.jsonl

python pipeline/run_pipeline.py \
  --store-config configs/stores/store_2.json \
  --output data/processed/store_2/generated_events.jsonl

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
python scripts/replay_events.py --file data/processed/store_1/generated_events.jsonl
python scripts/replay_events.py --file data/processed/store_2/generated_events.jsonl

curl http://localhost:8000/health
curl http://localhost:8000/stores/ST1008/metrics
curl http://localhost:8000/stores/ST1076/metrics
curl http://localhost:8000/stores/ST1008/conversion-debug
curl http://localhost:8000/stores/ST1076/conversion-debug
```
