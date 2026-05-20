from functools import lru_cache

from pydantic import AliasChoices, Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI SMM Bot"
    environment: str = Field(
        default="local",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
    )
    debug: bool = False

    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://smm:smm@localhost:5432/smm",
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_DSN"),
    )
    redis_url: RedisDsn = "redis://localhost:6379/0"
    celery_broker_url: RedisDsn = "redis://localhost:6379/1"
    celery_result_backend: RedisDsn = "redis://localhost:6379/2"

    open_router_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPEN_ROUTER_KEY", "OPENROUTER_API_KEY"),
    )
    telegram_bot_token: str | None = None
    bot_polling_timeout: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def parse_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def sync_database_url(self) -> str:
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
