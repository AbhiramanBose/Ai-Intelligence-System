from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class StoreZone(Base):
    __tablename__ = "store_zones"
    __table_args__ = (UniqueConstraint("store_id", "zone_id", name="uq_store_zone"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    zone_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(64), nullable=False)
    polygon_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
