# AI-Powered Store Intelligence System

An end-to-end Store Intelligence System that converts raw CCTV footage into structured behavioural events, ingests those events through production-ready APIs, and exposes retail intelligence such as store conversion, funnel movement, queue depth, dwell time, heatmap signals, anomaly warnings, and conversion-debug diagnostics.

The system is designed for the revised Purplle Tech Challenge dataset with multiple stores and role-based camera layouts.

## What this project does

The pipeline follows this flow:

```text
Raw CCTV footage
        ↓
YOLOv8 person detection + ByteTrack tracking
        ↓
Role-based camera processing
        ↓
Canonical behavioural events
        ↓
FastAPI event ingestion
        ↓
Metrics, funnel, heatmap, anomaly, and conversion-debug APIs
        ↓
Live dashboard / terminal dashboard
```

## Revised dataset support

The project supports two revised stores through external configuration files:

```text
configs/stores/store_1.json
configs/stores/store_2.json
```

The Python pipeline is generic. Store-specific information such as `store_id`, camera role, video path, zones, entry-source rules, queue rules, and POS correlation rules are kept in JSON config files.

This avoids hardcoding store logic inside Python code. In production, this configuration would come from a camera registry or store master table.

## Store 1

```text
Config: configs/stores/store_1.json
Store ID: ST1008
```

Camera mapping:

```text
CAM_1 → zone camera
CAM_2 → zone camera
CAM_3 → entry camera
CAM_5 → billing camera
```

Store 1 uses POS correlation because the revised POS CSV contains transactions for `ST1008`.

## Store 2

```text
Config: configs/stores/store_2.json
Store ID: ST1076
```

Camera mapping:

```text
ENTRY_1 → secondary entry camera
ENTRY_2 → primary entry source of truth
ZONE → zone camera
BILLING → billing camera
```

Store 2 has two entry cameras. The system suppresses duplicate session-counting events from the secondary entry camera to avoid inflating the unique visitor denominator.

## Business metric

The north-star business metric is offline store conversion rate:

```text
Offline Store Conversion Rate =
POS-confirmed converted visitors / unique customer sessions
```

A conversion is counted only when a billing-zone visitor can be matched to a POS transaction for the same store within the configured POS correlation window.

The system intentionally does not infer purchases only from CCTV. This avoids inflated conversion metrics.

## Key APIs

Start the API:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health:

```bash
curl http://localhost:8000/health
```

Metrics:

```bash
curl http://localhost:8000/stores/ST1008/metrics
curl http://localhost:8000/stores/ST1076/metrics
```

Funnel:

```bash
curl http://localhost:8000/stores/ST1008/funnel
curl http://localhost:8000/stores/ST1076/funnel
```

Heatmap:

```bash
curl http://localhost:8000/stores/ST1008/heatmap
curl http://localhost:8000/stores/ST1076/heatmap
```

Anomalies:

```bash
curl http://localhost:8000/stores/ST1008/anomalies
curl http://localhost:8000/stores/ST1076/anomalies
```

Conversion debug:

```bash
curl http://localhost:8000/stores/ST1008/conversion-debug
curl http://localhost:8000/stores/ST1076/conversion-debug
```

## POS normalization

The revised POS CSV is item-level, not transaction-level.

Run:

```bash
python scripts/seed_pos_transactions.py
```

The script normalizes the revised POS file from:

```text
101 raw item-level rows
```

to:

```text
24 transaction-level POS records
```

The normalized output is written to:

```text
data/processed/normalized_pos_transactions.csv
```

This file is ignored by Git because it is generated data.

## Running the CCTV pipeline

Store 1:

```bash
python pipeline/run_pipeline.py \
  --store-config configs/stores/store_1.json \
  --output data/processed/store_1/generated_events.jsonl
```

Expected summary:

```text
store_id: ST1008
event_count: 371
suppressed_entry_overlap_count: 0
```

Store 2:

```bash
python pipeline/run_pipeline.py \
  --store-config configs/stores/store_2.json \
  --output data/processed/store_2/generated_events.jsonl
```

Expected summary:

```text
store_id: ST1076
event_count: 138
suppressed_entry_overlap_count: 25
```

## Replaying generated events

Start the API first, then replay both stores:

```bash
python scripts/replay_events.py --file data/processed/store_1/generated_events.jsonl
python scripts/replay_events.py --file data/processed/store_2/generated_events.jsonl
```

Expected replay results:

```text
Store 1 accepted_count: 371
Store 2 accepted_count: 138
duplicate_count: 0
invalid_count: 0
```

## Final observed metrics

After resetting the DB, seeding POS, and replaying both stores:

### ST1008

```json
{
  "store_id": "ST1008",
  "unique_visitors": 4,
  "conversion_rate": 0.0,
  "current_queue_depth": 2,
  "abandonment_rate": 1.0
}
```

`ST1008` has POS data. It loaded 24 transactions, but no billing visitor matched a POS transaction within the configured time window. The system therefore reports zero conversion and marks unmatched billing visitors as abandoned.

### ST1076

```json
{
  "store_id": "ST1076",
  "unique_visitors": 31,
  "conversion_rate": 0.0,
  "current_queue_depth": 2,
  "abandonment_rate": 0.0
}
```

`ST1076` has no POS transactions in the supplied POS CSV. The system reports this transparently through `/conversion-debug` instead of inventing purchases.

## Known footage challenges handled

### Group entry

Multiple people entering close together are counted as separate tracked people. Entry events close together receive group-entry metadata.

### Staff movement

Staff-side movement is handled through configurable staff rules such as BOH zones, service zones, and staff camera flags.

### Re-entry

Re-entry is handled at the event and funnel level so the same visitor is not double-counted as a new funnel visitor.

### Partial occlusion

Low-confidence detections are retained with confidence metadata instead of being silently dropped.

### Billing queue buildup

Queue depth is estimated using a rolling median window to reduce noise from single-frame detections.

### Empty store periods

Empty-store API responses are tested and return stable zero-state metrics instead of failing.

### Camera angle overlap

Store 2 has overlapping entry cameras. The first camera listed in `entry_source_of_truth` is treated as the session-counting source of truth. Secondary entry-camera session events are suppressed.

## Health endpoint behaviour

For offline replayed CCTV data, `/health` may return:

```text
status: degraded
warning: STALE_FEED
```

This is expected because the event timestamps come from the historical challenge dataset. The database remains connected, and the warning indicates that no live event has arrived in the last 10 minutes.

## Testing

Run:

```bash
python -m pytest
```

Current result:

```text
24 passed
```

Run coverage:

```bash
python -m pytest --cov=app --cov=pipeline --cov-config=.coveragerc
```

Current result:

```text
TOTAL coverage: 86%
```

## Docker

Run:

```bash
docker compose down -v
docker compose up --build
```

Then verify:

```bash
curl http://localhost:8000/health
```

## Git hygiene

Raw and generated challenge data must not be committed.

Ignored paths include:

```text
data/raw/
data/processed/
*.mp4
*.mov
*.avi
*.mkv
storage/*.db
yolov8n.pt
```

Before committing, verify:

```bash
git status --short data/raw
git status --short data/processed
```

Expected: no output.

## Project structure

```text
app/
  main.py
  routers/
  services/
  schemas/
  models/

pipeline/
  run_pipeline.py
  zone_mapper.py

scripts/
  seed_pos_transactions.py
  replay_events.py
  postprocess_abandonment_events.py

configs/
  stores/
    store_1.json
    store_2.json

tests/
docs/
README.md
DESIGN.md
CHOICES.md
```

## Limitations

1. Full cross-camera person re-identification is not implemented. The system uses camera-role priority and source-of-truth rules for practical deduplication.
2. Staff classification is rule-based, not a trained uniform classifier.
3. Zone mapping uses broad business zones rather than brand-level shelf analytics.
4. POS correlation is time-window based because POS has no customer identity.
5. Conversion-drop anomaly detection requires historical baselines, which are not available in the supplied single-day dataset.
6. Offline replayed CCTV data naturally triggers stale-feed warnings in `/health`.

## Final validation snapshot

```text
Functional tests: 24 passed
Coverage: 86%
Store 1 events: 371 accepted
Store 2 events: 138 accepted
ST1008 POS transactions: 24 loaded
ST1008 conversion source: pos_correlation
ST1076 conversion source: no_pos_transactions_loaded
```
