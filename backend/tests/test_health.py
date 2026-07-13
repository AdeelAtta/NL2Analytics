from __future__ import annotations

from httpx import AsyncClient


class TestHealthEndpoints:
    async def test_liveness(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_readiness(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")
        assert "checks" in data
        assert "database" in data["checks"]

    async def test_version(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/v1/health/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "build" in data
        assert "environment" in data
        assert data["version"] == "0.1.0"
