from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient

from app.core.database import get_qdrant, get_session
from ke.api.main import create_ke_api
from ke.api.routes.schema import (
    _get_column_repo,
    _get_db_repo,
    _get_rel_repo,
    _get_schema_repo,
    _get_table_repo,
    _get_tenant_repo,
)
from ke.api.routes.sync import _get_metadata_sync_service
from ke.api.routes.vector import _get_vector_repo
from ke.services.sync import MetadataSyncService
from ke.stores.schema.repository import (
    ColumnRepository,
    DatabaseConfigRepository,
    RelationshipRepository,
    SchemaInfoRepository,
    TableRepository,
    TenantRepository,
)
from ke.stores.vector.repository import VectorRepository
from tests.ke.conftest import (
    _build_mock_repo,
    _make_db,
    _make_tenant,
)

_NOW = datetime.now(UTC)


def _make_mock_service(sync_result: dict | None = None, raises: type[Exception] | None = None) -> MagicMock:
    service = MagicMock(spec=MetadataSyncService)
    if raises:
        service.sync_database = AsyncMock(side_effect=raises("test error"))
    else:
        service.sync_database = AsyncMock(return_value=sync_result or {
            "database_id": "test-db-id",
            "sync_status": "synced",
            "added": 2,
            "changed": 1,
            "removed": 0,
            "unchanged": 5,
            "errors": [],
            "embedding": {"upserted": 15, "deleted": 0, "added_changed": 3, "removed": 0},
            "synced_at": _NOW.isoformat(),
        })
    return service


@pytest_asyncio.fixture
async def async_ke_client_sync() -> AsyncGenerator[AsyncClient, None]:
    tenant = _make_tenant()
    db = _make_db(tenant_id=tenant.id)
    tenant_repo = _build_mock_repo(TenantRepository, list_return=([tenant], 1), get_return=tenant)
    db_repo = _build_mock_repo(DatabaseConfigRepository, list_return=([db], 1), get_return=db)
    schema_repo = _build_mock_repo(SchemaInfoRepository, list_return=([], 0))
    table_repo = _build_mock_repo(TableRepository, list_return=([], 0))
    col_repo = _build_mock_repo(ColumnRepository, list_return=([], 0))
    rel_repo = _build_mock_repo(RelationshipRepository, list_return=([], 0))
    mock_qdrant = MagicMock(spec=AsyncQdrantClient)
    mock_sync_service = _make_mock_service()

    app = create_ke_api()
    mock_session = MagicMock()
    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_qdrant] = lambda: mock_qdrant
    app.dependency_overrides[_get_tenant_repo] = lambda: tenant_repo
    app.dependency_overrides[_get_db_repo] = lambda: db_repo
    app.dependency_overrides[_get_schema_repo] = lambda: schema_repo
    app.dependency_overrides[_get_table_repo] = lambda: table_repo
    app.dependency_overrides[_get_column_repo] = lambda: col_repo
    app.dependency_overrides[_get_rel_repo] = lambda: rel_repo
    app.dependency_overrides[_get_vector_repo] = lambda: VectorRepository(mock_qdrant)
    app.dependency_overrides[_get_metadata_sync_service] = lambda: mock_sync_service

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Service-Token": "ke_dev_token_2026"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def async_ke_client_sync_error() -> AsyncGenerator[AsyncClient, None]:
    tenant = _make_tenant()
    db = _make_db(tenant_id=tenant.id)
    tenant_repo = _build_mock_repo(TenantRepository, list_return=([tenant], 1), get_return=tenant)
    db_repo = _build_mock_repo(DatabaseConfigRepository, list_return=([db], 1), get_return=db)
    schema_repo = _build_mock_repo(SchemaInfoRepository, list_return=([], 0))
    table_repo = _build_mock_repo(TableRepository, list_return=([], 0))
    col_repo = _build_mock_repo(ColumnRepository, list_return=([], 0))
    rel_repo = _build_mock_repo(RelationshipRepository, list_return=([], 0))
    mock_qdrant = MagicMock(spec=AsyncQdrantClient)
    mock_sync_service = _make_mock_service(raises=ValueError)

    app = create_ke_api()
    mock_session = MagicMock()
    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_qdrant] = lambda: mock_qdrant
    app.dependency_overrides[_get_tenant_repo] = lambda: tenant_repo
    app.dependency_overrides[_get_db_repo] = lambda: db_repo
    app.dependency_overrides[_get_schema_repo] = lambda: schema_repo
    app.dependency_overrides[_get_table_repo] = lambda: table_repo
    app.dependency_overrides[_get_column_repo] = lambda: col_repo
    app.dependency_overrides[_get_rel_repo] = lambda: rel_repo
    app.dependency_overrides[_get_vector_repo] = lambda: VectorRepository(mock_qdrant)
    app.dependency_overrides[_get_metadata_sync_service] = lambda: mock_sync_service

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Service-Token": "ke_dev_token_2026"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def async_ke_client_sync_server_error() -> AsyncGenerator[AsyncClient, None]:
    tenant = _make_tenant()
    db = _make_db(tenant_id=tenant.id)
    tenant_repo = _build_mock_repo(TenantRepository, list_return=([tenant], 1), get_return=tenant)
    db_repo = _build_mock_repo(DatabaseConfigRepository, list_return=([db], 1), get_return=db)
    schema_repo = _build_mock_repo(SchemaInfoRepository, list_return=([], 0))
    table_repo = _build_mock_repo(TableRepository, list_return=([], 0))
    col_repo = _build_mock_repo(ColumnRepository, list_return=([], 0))
    rel_repo = _build_mock_repo(RelationshipRepository, list_return=([], 0))
    mock_qdrant = MagicMock(spec=AsyncQdrantClient)
    mock_sync_service = _make_mock_service(raises=RuntimeError)

    app = create_ke_api()
    mock_session = MagicMock()
    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_qdrant] = lambda: mock_qdrant
    app.dependency_overrides[_get_tenant_repo] = lambda: tenant_repo
    app.dependency_overrides[_get_db_repo] = lambda: db_repo
    app.dependency_overrides[_get_schema_repo] = lambda: schema_repo
    app.dependency_overrides[_get_table_repo] = lambda: table_repo
    app.dependency_overrides[_get_column_repo] = lambda: col_repo
    app.dependency_overrides[_get_rel_repo] = lambda: rel_repo
    app.dependency_overrides[_get_vector_repo] = lambda: VectorRepository(mock_qdrant)
    app.dependency_overrides[_get_metadata_sync_service] = lambda: mock_sync_service

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Service-Token": "ke_dev_token_2026"},
    ) as client:
        yield client


class TestSyncRoutes:
    async def test_sync_database_success(self, async_ke_client_sync: httpx.AsyncClient) -> None:
        resp = await async_ke_client_sync.post(
            "/v1/ke/sync/sync",
            json={"database_id": "test-db-id"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["database_id"] == "test-db-id"
        assert body["data"]["sync_status"] == "synced"
        assert body["data"]["added"] == 2
        assert body["data"]["changed"] == 1
        assert body["data"]["embedding"]["upserted"] == 15

    async def test_sync_database_with_password(self, async_ke_client_sync: httpx.AsyncClient) -> None:
        resp = await async_ke_client_sync.post(
            "/v1/ke/sync/sync",
            json={"database_id": "test-db-id", "password": "s3cr3t"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    async def test_sync_database_no_options(self, async_ke_client_sync: httpx.AsyncClient) -> None:
        resp = await async_ke_client_sync.post(
            "/v1/ke/sync/sync",
            json={"database_id": "test-db-id", "run_annotation": False, "run_inference": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    async def test_sync_database_no_auth(self, async_ke_client: httpx.AsyncClient) -> None:
        resp = await async_ke_client.post(
            "/v1/ke/sync/sync",
            json={"database_id": "test-db-id"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False

    async def test_sync_database_not_found(self, async_ke_client_sync_error: httpx.AsyncClient) -> None:
        resp = await async_ke_client_sync_error.post(
            "/v1/ke/sync/sync",
            json={"database_id": "nonexistent"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "KE-001"
        assert "database_id" in body["error"]["details"]

    async def test_sync_database_server_error(self, async_ke_client_sync_server_error: httpx.AsyncClient) -> None:
        resp = await async_ke_client_sync_server_error.post(
            "/v1/ke/sync/sync",
            json={"database_id": "test-db-id"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "KE-004"

    async def test_sync_database_missing_database_id(self, async_ke_client_sync: httpx.AsyncClient) -> None:
        resp = await async_ke_client_sync.post(
            "/v1/ke/sync/sync",
            json={},
        )
        assert resp.status_code == 422
