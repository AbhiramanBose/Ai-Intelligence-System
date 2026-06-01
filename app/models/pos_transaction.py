from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PosTransaction(Base):
    __tablename__ = "pos_transactions"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_pos_transaction_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    invoice_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    basket_value_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
