from sqlalchemy.orm import Session

from app.services.pos_correlation_service import PosCorrelationService


class FunnelService:
    def __init__(self, db: Session):
        self.db = db

    def get_funnel(self, store_id: str) -> dict:
        correlation = PosCorrelationService(self.db).get_summary(store_id)

        counts = [
            ("ENTRY", correlation["entry_count"]),
            ("PRODUCT_ZONE_VISIT", correlation["product_count"]),
            ("BILLING_QUEUE", correlation["billing_count"]),
            ("PURCHASE", correlation["converted_count"]),
        ]

        funnel = []
        previous_count = counts[0][1]

        for index, (stage, count) in enumerate(counts):
            if index == 0:
                dropoff = 0.0
            else:
                dropoff = (
                    round(((previous_count - count) / previous_count) * 100, 2)
                    if previous_count
                    else 0.0
                )

            funnel.append(
                {
                    "stage": stage,
                    "count": count,
                    "dropoff_percent": max(dropoff, 0.0),
                }
            )

            previous_count = count

        return {"store_id": store_id, "funnel": funnel}
