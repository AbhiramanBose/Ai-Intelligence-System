# Store Intelligence System

An end-to-end AI-powered retail store intelligence system that converts raw CCTV footage and POS transaction data into business metrics such as visitor count, product-zone engagement, billing queue activity, heatmap, anomalies, abandonment rate, and offline store conversion rate.

It processes multi-camera CCTV footage, generates structured behavioural events, ingests them through a FastAPI backend, correlates billing activity with POS transactions, and exposes production-style analytics APIs.

## Current Store

```text
Store ID: ST1008
Store Name: Brigade_Bangalore
City: Bangalore
Date: 10 April 2026
```

## High-Level Flow

```text
Raw CCTV footage
    ↓
YOLOv8 person detection
    ↓
ByteTrack tracking
    ↓
Camera-specific zone mapping
    ↓
Structured JSONL events
    ↓
POS enrichment and abandonment post-processing
    ↓
FastAPI event ingestion
    ↓
SQLite storage
    ↓
Metrics, funnel, heatmap, anomalies, health, conversion debug
    ↓
Live terminal dashboard
```

## Camera Mapping

```text
CAM_1: Main floor, top-wall skincare and central product-zone analytics
CAM_2: Main floor, bottom-wall makeup and central product-zone analytics
CAM_3: Entry / exit camera
CAM_4: Backroom / staff-side camera, excluded from customer metrics
CAM_5: Billing queue and POS correlation camera
```

Store-specific camera and zone assumptions are also documented in:

```text
configs/store_zones/ST1008.json
```

## Main Features

```text
1. CCTV-to-event detection pipeline
2. YOLOv8 person detection
3. ByteTrack person tracking
4. Camera-specific zone mapping
5. Structured event schema
6. 30-second ZONE_DWELL rule
7. Billing queue detection with queue depth
8. Explicit BILLING_QUEUE_ABANDON post-processing
9. FastAPI event ingestion
10. Idempotent storage by event_id
11. POS-based conversion correlation
12. Store metrics endpoint
13. Session-style funnel endpoint
14. Zone heatmap endpoint
15. Anomaly endpoint
16. Health endpoint with stale-feed detection
17. Conversion-debug endpoint for metric explainability
18. Live terminal dashboard
19. Structured request logging
20. Tests with 86% coverage
```

## Tech Stack

```text
Language: Python 3.11
API: FastAPI
Database: SQLite
ORM: SQLAlchemy
Validation: Pydantic
Computer Vision: YOLOv8
Tracking: ByteTrack
Video Processing: OpenCV
Dashboard: Rich terminal UI
Testing: pytest, pytest-cov
Containerization: Docker Compose
```

## Project Structure

```text
store-intelligence-starter/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── middleware.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   └── services/
│
├── pipeline/
│   ├── run_pipeline.py
│   └── zone_mapper.py
│
├── scripts/
│   ├── replay_events.py
│   ├── replay_events_realtime.py
│   ├── seed_pos_transactions.py
│   └── postprocess_abandonment_events.py
│
├── dashboard/
│   └── terminal_dashboard.py
│
├── configs/
│   └── store_zones/
│       └── ST1008.json
│
├── docs/
│   ├── METRIC_DEFINITIONS.md
│   └── RUNBOOK.md
│
├── data/
│   ├── fixtures/
│   ├── raw/
│   └── processed/
│
├── tests/
├── DESIGN.md
├── CHOICES.md
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

## Important Dataset Note

Raw challenge videos, raw POS files, generated event files, local database files, and downloaded model weights are intentionally excluded from Git.

Do not commit:

```text
data/raw/
*.mp4
*.mov
*.avi
*.mkv
yolov8n.pt
storage/store_intelligence.db
data/processed/generated_events.jsonl
data/processed/generated_events_with_pos.jsonl
data/processed/normalized_pos_transactions.csv
data/processed/detection_summary.json
```

These files are ignored through `.gitignore` and `.dockerignore`.

## Setup

Use Python 3.11.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Verify environment:

```bash
which python
python --version
```

Expected:

```text
Python 3.11.x
```

## Required Input Files

Place CCTV files here:

```text
data/raw/cctv/ST1008/CAM_1.mp4
data/raw/cctv/ST1008/CAM_2.mp4
data/raw/cctv/ST1008/CAM_3.mp4
data/raw/cctv/ST1008/CAM_4.mp4
data/raw/cctv/ST1008/CAM_5.mp4
```

Place POS CSV here:

```text
data/raw/pos/Brigade_Bangalore_10_April_26.csv
```

## Run API Locally

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Run with Docker

```bash
docker compose up --build
```

Then verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/stores/ST1008/metrics
```

## Generate CCTV Events

```bash
python pipeline/run_pipeline.py \
  --store-id ST1008 \
  --cam1 data/raw/cctv/ST1008/CAM_1.mp4 \
  --cam2 data/raw/cctv/ST1008/CAM_2.mp4 \
  --cam3 data/raw/cctv/ST1008/CAM_3.mp4 \
  --cam4 data/raw/cctv/ST1008/CAM_4.mp4 \
  --cam5 data/raw/cctv/ST1008/CAM_5.mp4 \
  --output data/processed/generated_events.jsonl
```

This creates:

```text
data/processed/generated_events.jsonl
data/processed/detection_summary.json
```

Current observed run:

```text
input CCTV events: 334
```

## Normalize and Seed POS Transactions

```bash
python scripts/seed_pos_transactions.py
```

This creates:

```text
data/processed/normalized_pos_transactions.csv
```

The POS CSV is normalized into transaction-level rows and inserted into SQLite.

Current observed run:

```text
Normalized POS transactions: 24
Inserted: 24
Skipped duplicates: 0
```

## Add Billing Queue Abandonment Events

After CCTV events and POS transactions are available, run:

```bash
python scripts/postprocess_abandonment_events.py \
  --events data/processed/generated_events.jsonl \
  --pos data/processed/normalized_pos_transactions.csv \
  --output data/processed/generated_events_with_pos.jsonl
```

This appends explicit `BILLING_QUEUE_ABANDON` events for billing visitors who do not match a POS transaction within the five-minute conversion window.

Current observed run:

```text
input_event_count: 334
transaction_count: 24
abandon_event_count: 12
output_event_count: 346
```

## Replay Events into API

Replay the POS-enriched event file:

```bash
python scripts/replay_events.py --file data/processed/generated_events_with_pos.jsonl
```

Expected clean replay:

```json
{
  "accepted_count": 346,
  "duplicate_count": 0,
  "invalid_count": 0
}
```

If the same file is replayed again, duplicates are expected. That confirms ingestion idempotency.

## API Endpoints

### Health

```bash
curl http://localhost:8000/health
```

Returns service status, database status, latest event timestamp per store, and stale-feed warnings.

### Metrics

```bash
curl http://localhost:8000/stores/ST1008/metrics
```

Latest observed response:

```json
{
  "store_id": "ST1008",
  "unique_visitors": 4,
  "conversion_rate": 0.0,
  "avg_dwell_per_zone": {
    "ZONE_FOH": 62850.55,
    "ZONE_BILLING_QUEUE": 30622.5
  },
  "current_queue_depth": 1,
  "abandonment_rate": 1.0
}
```

### Funnel

```bash
curl http://localhost:8000/stores/ST1008/funnel
```

Latest observed response:

```json
{
  "store_id": "ST1008",
  "funnel": [
    {
      "stage": "ENTRY",
      "count": 4,
      "dropoff_percent": 0.0
    },
    {
      "stage": "PRODUCT_ZONE_VISIT",
      "count": 4,
      "dropoff_percent": 0.0
    },
    {
      "stage": "BILLING_QUEUE",
      "count": 4,
      "dropoff_percent": 0.0
    },
    {
      "stage": "PURCHASE",
      "count": 0,
      "dropoff_percent": 100.0
    }
  ]
}
```

### Heatmap

```bash
curl http://localhost:8000/stores/ST1008/heatmap
```

Returns zone-level visit count, average dwell time, normalized heat score, and data confidence.

`data_confidence` is marked `LOW` when the observed session count is below 20.

### Anomalies

```bash
curl http://localhost:8000/stores/ST1008/anomalies
```

Detects operational anomalies such as stale feed, billing queue spike, dead zones, and unavailable conversion baseline.

For the challenge dataset, `STALE_FEED` is expected after replay because the CCTV-derived event timestamps are historical.

### Conversion Debug

```bash
curl http://localhost:8000/stores/ST1008/conversion-debug
```

Latest observed response:

```json
{
  "store_id": "ST1008",
  "entry_count": 4,
  "product_count": 4,
  "billing_count": 4,
  "converted_count": 0,
  "abandoned_count": 4,
  "transaction_count": 24,
  "matched_transaction_count": 0,
  "unmatched_transaction_count": 24,
  "matched_transactions": [],
  "conversion_source": "pos_correlation",
  "abandonment_source": "unmatched_billing_visitors"
}
```

This endpoint exists to make the north-star metric auditable.

## POS Correlation Rule

The system uses POS-confirmed conversion:

```text
conversion_rate = POS-confirmed converted visitors / unique customer sessions
```

A conversion is counted only when a visitor is detected in the billing queue within five minutes before a POS transaction timestamp for the same store.

Billing queue presence alone is not treated as purchase.

For the provided ST1008 run, billing events occur around:

```text
2026-04-10T14:39Z to 2026-04-10T14:40Z
```

The nearest POS transactions are outside the five-minute conversion window. Therefore, the system correctly reports:

```text
conversion_rate = 0.0
PURCHASE count = 0
abandonment_rate = 1.0
```

This is intentional. The system avoids falsely inflating offline conversion.

## Live Terminal Dashboard

Terminal 1, start API:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2, start dashboard:

```bash
python dashboard/terminal_dashboard.py --store-id ST1008 --refresh-seconds 2
```

Terminal 3, replay events slowly:

```bash
python scripts/replay_events_realtime.py \
  --file data/processed/generated_events_with_pos.jsonl \
  --batch-size 10 \
  --delay-seconds 1.5
```

The dashboard updates metrics, funnel, heatmap, anomalies, and health while events are being ingested.

## Run Tests

```bash
python -m pytest
```

Expected:

```text
24 passed
```

## Run Coverage

```bash
python -m pytest --cov=app --cov=pipeline --cov-config=.coveragerc
```

Expected:

```text
86% coverage
```

## Edge Cases Covered by Tests

```text
1. Empty store / zero-traffic behavior
2. All-staff movement excluded from customer metrics
3. Re-entry does not double-count the funnel
4. Zero-purchase behavior
5. POS-confirmed conversion
6. Billing abandonment post-processing
7. Ingestion idempotency
8. Event schema validation
9. Health endpoint
10. Zone mapping
```

## Documentation

```text
DESIGN.md
CHOICES.md
docs/METRIC_DEFINITIONS.md
docs/RUNBOOK.md
configs/store_zones/ST1008.json
```

## Known Limitations

1. Full cross-camera person re-identification is not implemented in v1.
2. Staff handling uses camera and zone assumptions rather than a trained uniform classifier.
3. Conversion drop versus seven-day average is not emitted without historical baseline data.
4. The challenge dataset is short, so heatmap confidence is intentionally conservative.
5. Generated event files and raw challenge data are not committed to Git.

## Final Verification Checklist

Before submission:

```bash
python -m pytest
python -m pytest --cov=app --cov=pipeline --cov-config=.coveragerc
docker compose up --build
curl http://localhost:8000/health
curl http://localhost:8000/stores/ST1008/metrics
```

Before pushing to GitHub, ensure sensitive/generated files are not staged:

```bash
git diff --cached --name-only | grep -E "data/raw|\\.mp4|\\.mov|\\.avi|\\.mkv|yolov8n.pt|store_intelligence.db|generated_events|generated_events_with_pos|normalized_pos_transactions|detection_summary"
```

Expected: no output.

