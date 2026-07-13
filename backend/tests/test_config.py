from __future__ import annotations

from app.core.config import Settings, get_settings


class TestConfig:
    def test_settings_defaults(self) -> None:
        settings = Settings()
        assert settings.app_name == "SchemaIntern Backend"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.environment == "development"

    def test_settings_from_env(self, monkeypatch):  # type: ignore[no-untyped-def]
        monkeypatch.setenv("APP_NAME", "Test App")
        monkeypatch.setenv("ENVIRONMENT", "testing")
        settings = Settings()
        assert settings.app_name == "Test App"
        assert settings.environment == "testing"

    def test_get_settings_singleton(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
