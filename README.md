# Store Intelligence System

An end-to-end retail store intelligence system that converts CCTV footage and POS data into business metrics such as visitor count, product-zone engagement, billing queue activity, heatmap, anomalies, and offline store conversion rate.

The project is built for the UpGrad Store Intelligence Challenge. It processes multi-camera CCTV footage from the Brigade Bangalore store, generates structured events, ingests them through a FastAPI backend, and exposes analytics endpoints.

## Current Store

```text
Store ID: ST1008
Store Name: Brigade_Bangalore
City: Bangalore
Date: 10 April 2026
```

## High-Level Flow

```text
CCTV footage
    ↓
YOLOv8 person detection
    ↓
ByteTrack tracking
    ↓
Camera-specific zone mapping
    ↓
Structured JSONL events
    ↓
FastAPI event ingestion
    ↓
SQLite storage
    ↓
Metrics, funnel, heatmap, anomalies, health
    ↓
POS correlation for conversion
```

## Camera Mapping

```text
CAM_1: Top-wall skincare and central product-zone analytics
CAM_2: Bottom-wall makeup and central product-zone analytics
CAM_3: Entry / exit camera
CAM_4: Backroom / staff-side camera, excluded from customer metrics
CAM_5: Billing queue and POS correlation camera
```

## Main Features

```text
1. CCTV-to-event pipeline
2. Event ingestion API
3. Idempotent event storage using event_id
4. Store metrics API
5. Session-style funnel API
6. Zone heatmap API
7. Anomaly API
8. Health API with stale-feed detection
9. POS CSV normalization
10. POS-based conversion correlation
11. Tests with coverage above 70%
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
Testing: pytest, pytest-cov
Containerization: Docker Compose
```

## Project Structure

```text
store-intelligence-starter/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   └── services/
│
├── pipeline/
│   ├── run_pipeline.py
│   ├── zone_mapper.py
│   └── supporting pipeline modules
│
├── scripts/
│   ├── replay_events.py
│   └── seed_pos_transactions.py
│
├── data/
│   ├── raw/
│   │   ├── cctv/ST1008/
│   │   └── pos/
│   └── processed/
│
├── tests/
├── DESIGN.md
├── CHOICES.md
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

## Setup

Use Python 3.11.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
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

## Normalize and Seed POS Transactions

```bash
python scripts/seed_pos_transactions.py
```

This creates:

```text
data/processed/normalized_pos_transactions.csv
```

The POS CSV is item-level. The script converts it into transaction-level rows and inserts them into SQLite.

## Replay Events into API

```bash
python scripts/replay_events.py --file data/processed/generated_events.jsonl
```

## API Endpoints

### Health

```bash
curl http://localhost:8000/health
```

### Metrics

```bash
curl http://localhost:8000/stores/ST1008/metrics
```

Returns:

```json
{
  "store_id": "ST1008",
  "unique_visitors": 6,
  "conversion_rate": 0.0,
  "avg_dwell_per_zone": {
    "ZONE_FOH": 33755.93,
    "ZONE_BILLING_QUEUE": 22496.2,
    "ZONE_CENTER_MAKEUP_UNIT": 10010.0
  },
  "current_queue_depth": 1,
  "abandonment_rate": 0.0
}
```

### Funnel

```bash
curl http://localhost:8000/stores/ST1008/funnel
```

Returns a session-style funnel:

```text
ENTRY
PRODUCT_ZONE_VISIT
BILLING_QUEUE
PURCHASE
```

### Heatmap

```bash
curl http://localhost:8000/stores/ST1008/heatmap
```

Returns zone-level visit count, average dwell time, heat score, and data confidence.

### Anomalies

```bash
curl http://localhost:8000/stores/ST1008/anomalies
```

Detects stale feed and queue-related anomalies.

## POS Correlation Rule

A purchase conversion is counted only when a visitor is detected in the billing queue within five minutes before a POS transaction timestamp.

For the provided demo run, CCTV billing events occur around:

```text
2026-04-10T14:39Z to 2026-04-10T14:40Z
```

The nearest POS transactions are approximately 15 minutes away from this CCTV billing window. Therefore, no transaction satisfies the five-minute correlation rule, and the system correctly reports:

```text
conversion_rate = 0.0
PURCHASE count = 0
```

This is intentional. The system avoids falsely inflating conversion.

## Run Tests

```bash
python -m pytest
```

Expected:

```text
13 passed
```

## Run Coverage

```bash
python -m pytest --cov=app --cov=pipeline --cov-config=.coveragerc
```

Expected coverage:

```text
86% or above
```

## Notes

1. The CCTV pipeline uses broad analytics zones rather than overly granular brand-level zones.
2. CAM_4 is treated as a backroom/staff-side camera and excluded from customer metrics.
3. The current cross-camera visitor identity is approximate. CAM_3 provides entry count, while CAM_1, CAM_2, and CAM_5 provide zone and billing signals.
4. POS-based conversion is stricter than billing fallback and is used for final metrics.
