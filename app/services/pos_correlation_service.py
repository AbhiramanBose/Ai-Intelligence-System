from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.pos_transaction import PosTransaction


NON_PRODUCT_ZONES = {
    None,
    "ZONE_FOH",
    "ZONE_BILLING",
    "ZONE_BILLING_QUEUE",
    "ZONE_PMU",
    "ZONE_BACKROOM",
    "ZONE_OUTSIDE_CORRIDOR",
    "ZONE_ENTRY_EXIT",
}


def to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class PosCorrelationService:
    def __init__(self, db: Session):
        self.db = db

    def get_summary(self, store_id: str) -> dict:
        events = (
            self.db.query(Event)
            .filter(Event.store_id == store_id, Event.is_staff.is_(False))
            .order_by(Event.timestamp.asc())
            .all()
        )

        transactions = (
            self.db.query(PosTransaction)
            .filter(PosTransaction.store_id == store_id)
            .order_by(PosTransaction.timestamp.asc())
            .all()
        )

        entry_visitors = {
            event.visitor_id
            for event in events
            if event.event_type in {"ENTRY", "REENTRY"}
        }

        active_visitors = {
            event.visitor_id
            for event in events
            if event.event_type in {
                "ENTRY",
                "REENTRY",
                "ZONE_ENTER",
                "ZONE_DWELL",
                "BILLING_QUEUE_JOIN",
            }
        }

        product_visitors = {
            event.visitor_id
            for event in events
            if event.event_type in {"ZONE_ENTER", "ZONE_DWELL"}
            and event.zone_id not in NON_PRODUCT_ZONES
        }

        billing_events = [
            event for event in events if event.event_type == "BILLING_QUEUE_JOIN"
        ]

        billing_visitors = {event.visitor_id for event in billing_events}

        explicit_abandoned_visitors = {
            event.visitor_id
            for event in events
            if event.event_type == "BILLING_QUEUE_ABANDON"
        }

        entry_count = len(entry_visitors) or len(active_visitors)
        product_count = min(len(product_visitors), entry_count) if entry_count else 0
        billing_count = min(len(billing_visitors), product_count) if product_count else 0

        converted_visitors: set[str] = set()
        matched_transactions: list[str] = []
        unmatched_transactions: list[str] = []

        for transaction in transactions:
            transaction_time = to_utc_naive(transaction.timestamp)
            window_start = transaction_time - timedelta(minutes=5)

            candidates = []

            for event in billing_events:
                event_time = to_utc_naive(event.timestamp)

                if (
                    window_start <= event_time <= transaction_time
                    and event.visitor_id not in converted_visitors
                ):
                    candidates.append(event)

            if not candidates:
                unmatched_transactions.append(transaction.transaction_id)
                continue

            selected_event = max(candidates, key=lambda event: to_utc_naive(event.timestamp))
            converted_visitors.add(selected_event.visitor_id)
            matched_transactions.append(transaction.transaction_id)

        if transactions:
            converted_count = min(len(converted_visitors), billing_count)
            abandoned_count = max(billing_count - converted_count, 0)
            conversion_source = "pos_correlation"
            abandonment_source = "unmatched_billing_visitors"
        else:
            # Conversion is intentionally POS-confirmed only.
            # A billing queue visit without a POS transaction is not treated as a purchase.
            converted_count = 0
            abandoned_count = min(len(explicit_abandoned_visitors), billing_count)
            conversion_source = "no_pos_transactions_loaded"
            abandonment_source = "explicit_abandon_events"

        return {
            "store_id": store_id,
            "entry_count": entry_count,
            "product_count": product_count,
            "billing_count": billing_count,
            "converted_count": converted_count,
            "abandoned_count": abandoned_count,
            "transaction_count": len(transactions),
            "matched_transaction_count": len(matched_transactions),
            "unmatched_transaction_count": len(unmatched_transactions),
            "matched_transactions": matched_transactions,
            "conversion_source": conversion_source,
            "abandonment_source": abandonment_source,
        }
