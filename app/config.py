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
    GEMINI_MODEL: str = "gemini-2.5-flash"

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

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
