from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so SQLAlchemy registers metadata.
    from app.models.event import Event  # noqa: F401
    from app.models.pos_transaction import PosTransaction  # noqa: F401
    from app.models.store_zone import StoreZone  # noqa: F401
    from app.models.anomaly import Anomaly  # noqa: F401
    Base.metadata.create_all(bind=engine)
