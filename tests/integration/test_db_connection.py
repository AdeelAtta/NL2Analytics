"""Integration test for PostgreSQL database connection.

Skipped by default unless INTEGRATION_TEST=1 is set.
"""

import os

import pytest
from sqlalchemy import text

from app.core.database import engine

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.environ.get("INTEGRATION_TEST") != "1",
        reason="Set INTEGRATION_TEST=1 to run integration tests",
    ),
]


async def test_postgres_connection() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1 AS val"))
        row = result.fetchone()
        assert row is not None
        assert row._mapping["val"] == 1
