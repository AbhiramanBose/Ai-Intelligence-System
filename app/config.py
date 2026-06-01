from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Store Intelligence API"
    app_env: str = Field(default="local", alias="APP_ENV")
    database_url: str = Field(default="sqlite:///./storage/store_intelligence.db", alias="DATABASE_URL")
    default_store_id: str = Field(default="ST1008", alias="STORE_ID")
    stale_feed_minutes: int = 10

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
