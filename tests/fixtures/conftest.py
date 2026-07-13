from collections.abc import AsyncGenerator
from typing import Any

import pytest


@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {"app_name": "SchemaIntern Backend", "debug": False, "version": "0.1.0"}


@pytest.fixture
def sample_db_url() -> str:
    return "postgresql+asyncpg://user:pass@localhost:5432/schemaintern"
