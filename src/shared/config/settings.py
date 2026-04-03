from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in src/ first, then project root
_env_file = Path(__file__).resolve().parents[2] / ".env"  # src/.env
if not _env_file.exists():
    _env_file = Path(__file__).resolve().parents[3] / ".env"  # project root/.env


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_file),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    postgres_user: str = "propyte"
    postgres_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "propyte_data"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_echo: bool = False

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    # S3
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Proxy
    proxy_dataimplulse_url: str = ""
    proxy_brightdata_url: str = ""
    proxy_budget_mb: float = 500.0  # max MB per scrape session (default 500 MB)

    # Anthropic
    anthropic_api_key: str = ""

    # Supabase (archivo permanente)
    supabase_url: str = ""          # https://xxx.supabase.co
    supabase_service_key: str = ""  # service_role key (bypasses RLS)

    # Alerts
    alert_webhook_url: str = ""  # Slack/Discord/Telegram webhook

    # Auth
    admin_password: str = ""

    # App
    environment: str = "development"
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"


settings = Settings()
