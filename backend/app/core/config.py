import logging
import uuid
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "SchemaIntern Backend"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Database
    postgres_dsn: str = "postgresql+asyncpg://schemaintern:schemaintern_dev@localhost:5432/schemaintern"
    postgres_dsn_sync: str = "postgresql://schemaintern:schemaintern_dev@localhost:5432/schemaintern"


    # Auth
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_token_ttl: int = 3600
    api_keys: list[str] = []

    # Observability
    otel_endpoint: str = ""
    otel_service_name: str = "ke-api"
    enable_tracing: bool = True
    log_level: str = "INFO"
    sentry_dsn: str = ""
    enable_sentry: bool = False

    # Prometheus
    enable_metrics: bool = True
    metrics_endpoint: str = "/metrics"

    # Embeddings (Hugging Face)
    hf_token: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024

    # LLM Inference
    openai_api_key: str = ""
    openai_org_id: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    _validate_settings(settings)
    return settings


_DEFAULT_CREDENTIAL_WORDS = ("schemaintern_dev", "localhost", "change-me")


def _validate_settings(settings: Settings) -> None:
    if not settings.jwt_secret:
        generated = uuid.uuid4().hex
        logger.warning(
            "JWT_SECRET not set. Generated ephemeral secret: %s. "
            "Set JWT_SECRET environment variable for production.",
            generated,
        )
        settings.jwt_secret = generated

    is_prod = settings.environment == "production"
    if is_prod:
        checks = (("POSTGRES_DSN", settings.postgres_dsn),)
        for dsn_name, dsn in checks:
            if dsn and any(w in dsn.lower() for w in _DEFAULT_CREDENTIAL_WORDS):
                logger.warning(
                    "%s appears to use default credentials. "
                    "Set a strong password via environment variable for production.",
                    dsn_name,
                )
        weak_jwt = any(w in settings.jwt_secret.lower() for w in ("change", "secret", "default"))
        if settings.jwt_secret and weak_jwt:
            logger.warning(
                "JWT_SECRET appears to be a weak default. "
                "Set a strong random value via environment variable."
            )
