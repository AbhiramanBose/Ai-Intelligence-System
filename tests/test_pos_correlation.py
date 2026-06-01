# PROMPT:
# Generate pytest tests for POS-to-billing correlation using a five-minute transaction window.
#
# CHANGES MADE:
# Added direct SQLAlchemy setup with isolated store IDs and assertions for matched and unmatched POS transactions.

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal, init_db
from app.models.event import Event
from app.models.pos_transaction import PosTransaction
from app.services.pos_correlation_service import PosCorrelationService


def add_event(db, *, store_id, visitor_id, event_type, timestamp, zone_id=None):
    db.add(
        Event(
            event_id=f"test-{store_id}-{visitor_id}-{event_type}-{timestamp.timestamp()}",
            store_id=store_id,
            camera_id="CAM_TEST",
            visitor_id=visitor_id,
            event_type=event_type,
            timestamp=timestamp,
            zone_id=zone_id,
            dwell_ms=0,
            is_staff=False,
            confidence=0.9,
            metadata_json="{}",
        )
    )


def add_transaction(db, *, store_id, transaction_id, timestamp):
    db.add(
        PosTransaction(
            transaction_id=transaction_id,
            invoice_number=transaction_id,
            store_id=store_id,
            store_name="Test Store",
            timestamp=timestamp,
            basket_value_inr=500.0,
            item_count=1,
            unique_items=1,
        )
    )


def test_pos_transaction_matches_billing_event_within_five_minutes():
    init_db()
    db = SessionLocal()
    store_id = "POS_TEST_MATCH"

    try:
        db.query(Event).filter(Event.store_id == store_id).delete()
        db.query(PosTransaction).filter(PosTransaction.store_id == store_id).delete()

        entry_time = datetime(2026, 4, 10, 14, 39, 0, tzinfo=timezone.utc)
        billing_time = datetime(2026, 4, 10, 14, 40, 0, tzinfo=timezone.utc)
        transaction_time = billing_time + timedelta(minutes=3)

        add_event(db, store_id=store_id, visitor_id="VIS_ENTRY_1", event_type="ENTRY", timestamp=entry_time)
        add_event(db, store_id=store_id, visitor_id="VIS_PRODUCT_1", event_type="ZONE_ENTER", timestamp=entry_time, zone_id="ZONE_TOP_WALL_SKINCARE")
        add_event(db, store_id=store_id, visitor_id="VIS_BILLING_1", event_type="BILLING_QUEUE_JOIN", timestamp=billing_time, zone_id="ZONE_BILLING_QUEUE")
        add_transaction(db, store_id=store_id, transaction_id="TXN_MATCH_1", timestamp=transaction_time)

        db.commit()

        summary = PosCorrelationService(db).get_summary(store_id)

        assert summary["entry_count"] == 1
        assert summary["billing_count"] == 1
        assert summary["transaction_count"] == 1
        assert summary["matched_transaction_count"] == 1
        assert summary["converted_count"] == 1
        assert summary["conversion_source"] == "pos_correlation"

    finally:
        db.query(Event).filter(Event.store_id == store_id).delete()
        db.query(PosTransaction).filter(PosTransaction.store_id == store_id).delete()
        db.commit()
        db.close()


def test_pos_transaction_outside_five_minute_window_does_not_convert():
    init_db()
    db = SessionLocal()
    store_id = "POS_TEST_NO_MATCH"

    try:
        db.query(Event).filter(Event.store_id == store_id).delete()
        db.query(PosTransaction).filter(PosTransaction.store_id == store_id).delete()

        entry_time = datetime(2026, 4, 10, 14, 39, 0, tzinfo=timezone.utc)
        billing_time = datetime(2026, 4, 10, 14, 40, 0, tzinfo=timezone.utc)
        transaction_time = billing_time + timedelta(minutes=10)

        add_event(db, store_id=store_id, visitor_id="VIS_ENTRY_1", event_type="ENTRY", timestamp=entry_time)
        add_event(db, store_id=store_id, visitor_id="VIS_PRODUCT_1", event_type="ZONE_ENTER", timestamp=entry_time, zone_id="ZONE_TOP_WALL_SKINCARE")
        add_event(db, store_id=store_id, visitor_id="VIS_BILLING_1", event_type="BILLING_QUEUE_JOIN", timestamp=billing_time, zone_id="ZONE_BILLING_QUEUE")
        add_transaction(db, store_id=store_id, transaction_id="TXN_NO_MATCH_1", timestamp=transaction_time)

        db.commit()

        summary = PosCorrelationService(db).get_summary(store_id)

        assert summary["entry_count"] == 1
        assert summary["billing_count"] == 1
        assert summary["transaction_count"] == 1
        assert summary["matched_transaction_count"] == 0
        assert summary["converted_count"] == 0
        assert summary["conversion_source"] == "pos_correlation"

    finally:
        db.query(Event).filter(Event.store_id == store_id).delete()
        db.query(PosTransaction).filter(PosTransaction.store_id == store_id).delete()
        db.commit()
        db.close()
