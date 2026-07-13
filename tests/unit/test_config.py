"""Tests for the backend Settings class.

These tests validate the real Settings class from app.core.config,
not a separate test-only model. This ensures our configuration
defaults and env loading work correctly.
"""

from app.core.config import Settings, get_settings


def test_settings_default_app_name() -> None:
    settings = Settings()
    assert settings.app_name == "SchemaIntern Backend"


def test_settings_default_debug() -> None:
    settings = Settings()
    assert settings.debug is False


def test_settings_default_version() -> None:
    settings = Settings()
    assert settings.app_version == "0.1.0"


def test_settings_default_postgres_dsn() -> None:
    settings = Settings()
    assert "postgresql+asyncpg://" in settings.postgres_dsn


def test_settings_get_settings_singleton() -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_cors_origins() -> None:
    settings = Settings()
    assert "http://localhost:3000" in settings.cors_origins


def test_settings_jwt_defaults() -> None:
    settings = Settings()
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_secret == ""
