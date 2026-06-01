#!/usr/bin/env python3
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models.store_zone import StoreZone


def main() -> None:
    init_db()
    path = Path("configs/stores/ST1008.json")
    data = json.loads(path.read_text())
    db: Session = SessionLocal()
    try:
        for zone in data["zones"]:
            existing = db.query(StoreZone).filter(
                StoreZone.store_id == data["store_id"],
                StoreZone.zone_id == zone["zone_id"],
            ).first()
            if existing:
                continue
            db.add(StoreZone(
                store_id=data["store_id"],
                zone_id=zone["zone_id"],
                display_name=zone["display_name"],
                zone_type=zone["zone_type"],
                polygon_json=json.dumps(zone.get("polygon", [])),
            ))
        db.commit()
        print("Seeded store layout.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
