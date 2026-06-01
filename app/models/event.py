from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_events_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    visitor_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    zone_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    dwell_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
