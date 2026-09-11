import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    DATABASE_URL: str = "sqlite+aiosqlite:///./memoai.db"

    # Authentication
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    # Ordered fallback chain across models. Gemini free tier quotas are
    # enforced per model per day, so the provider switches to the next
    # model when one hits its quota or is retired.
    GEMINI_MODELS: Annotated[list[str], NoDecode] = [
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    ]

    GROQ_API_KEY: str = ""

    # Object storage (Backblaze B2). Leave the keys empty to use local
    # fallback storage (data/uploads) for development and tests.
    B2_ENDPOINT_URL: str = "https://s3.us-west-004.backblazeb2.com"
    B2_KEY_ID: str = ""
    B2_APPLICATION_KEY: str = ""
    B2_BUCKET_NAME: str = ""
    STORAGE_DIR: str = "data/uploads"

    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["*"]

    ENVIRONMENT: str = "development"
    PORT: int = 8000

    # Force IPv4 for all outbound connections. Needed on dev hosts whose
    # IPv6 route is broken: boto3/httpx would otherwise pick IPv6 first and
    # hang on dual-stack endpoints (e.g. Backblaze B2).
    NET_IPV4_ONLY: bool = False

    @field_validator("CORS_ORIGINS", "GEMINI_MODELS", mode="before")
    @classmethod
    def parse_csv_or_json_list(cls, value):
        if isinstance(value, str):
            if value.startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
