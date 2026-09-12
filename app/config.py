import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode

_WEAK_JWT_PLACEHOLDERS = (
    "changeme",
    "your-random-jwt-secret",
    "your_jwt_secret",
    "your-jwt-secret",
    "test-secret",
)


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    DATABASE_URL: str = "sqlite+aiosqlite:///./memoai.db"

    # Authentication
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Falls back to JWT_SECRET when empty.
    VERIFICATION_TOKEN_SECRET: str = ""
    RESET_PASSWORD_TOKEN_SECRET: str = ""

    # Email delivery (Resend). REQUIRED in production; logged in dev/tests.
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "MemoAI <noreply@memo-ai.app>"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    # Ordered fallback chain across models (free-tier quotas are per model).
    GEMINI_MODELS: Annotated[list[str], NoDecode] = [
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    ]

    GROQ_API_KEY: str = ""

    # Object storage (Backblaze B2). Empty keys -> local fallback storage.
    B2_ENDPOINT_URL: str = "https://s3.us-west-004.backblazeb2.com"
    B2_KEY_ID: str = ""
    B2_APPLICATION_KEY: str = ""
    B2_BUCKET_NAME: str = ""
    # Optional; derived from B2_ENDPOINT_URL when empty.
    B2_REGION: str = ""
    STORAGE_DIR: str = "data/uploads"

    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["*"]

    ENVIRONMENT: str = "development"
    PORT: int = 8000

    # Rate limiting (in-memory, per process)
    RATE_LIMITING_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "300/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_AI: str = "60/minute"
    RATE_LIMIT_UPLOAD: str = "10/minute"

    MAX_UPLOAD_BYTES: int = 300 * 1024 * 1024

    # Force IPv4 for all outbound connections (broken IPv6 routes hang on
    # dual-stack endpoints such as Backblaze B2).
    NET_IPV4_ONLY: bool = False

    @field_validator("CORS_ORIGINS", "GEMINI_MODELS", mode="before")
    @classmethod
    def parse_csv_or_json_list(cls, value):
        if isinstance(value, str):
            if value.startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, value):
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long")
        lowered = value.lower()
        for placeholder in _WEAK_JWT_PLACEHOLDERS:
            if placeholder in lowered:
                raise ValueError("JWT_SECRET must not contain a weak placeholder value")
        return value

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, value):
        value = (value or "development").strip().lower()
        if value not in {"development", "production"}:
            raise ValueError("ENVIRONMENT must be 'development' or 'production'")
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
