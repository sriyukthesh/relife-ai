from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load the .env that lives next to the backend so the MODEL_API_KEY / MUSE_MODEL
# are picked up no matter which directory uvicorn is launched from.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if not _ENV_FILE.is_file():
    _ENV_FILE = Path(".env")


import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Support SQLite for local dev when PostgreSQL/Docker is unavailable
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./secondlife.db")
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173"

    # Meta Model API. Env var name follows Meta's cookbook: MODEL_API_KEY.
    meta_api_key: str = Field("", validation_alias="MODEL_API_KEY")
    meta_base_url: str = "https://api.meta.ai/v1"
    muse_model: str = "muse-spark-1.3"

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_currency: Literal["USD"] = "USD"
    paypal_seller_email: str = ""
    channel3_api_key: str = Field("", validation_alias="CHANNEL3_API_KEY")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
