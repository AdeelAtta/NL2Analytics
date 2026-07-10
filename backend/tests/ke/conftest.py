from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

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
from ke.models.schema import (
    Column,
    DatabaseConfig,
    Relationship,
    SchemaInfo,
    Table,
    Tenant,
)
from ke.stores.schema.repository import (
    ColumnRepository,
    DatabaseConfigRepository,
    RelationshipRepository,
    SchemaInfoRepository,
    TableRepository,
    TenantRepository,
)
from ke.stores.vector.repository import VectorRepository

_NOW = datetime.now(UTC)


def _make_tenant() -> Tenant:
    return Tenant(
        id=str(uuid4()),
        name="Test Tenant",
        slug="test-tenant",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_db(tenant_id: str) -> DatabaseConfig:
    return DatabaseConfig(
        id=str(uuid4()),
        tenant_id=tenant_id,
        name="Test DB",
        db_type="postgresql",
        connection_hash="abc123",
        host="localhost",
        port=5432,
        database_name="testdb",
        username="test_user",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_schema_info(database_id: str) -> SchemaInfo:
    return SchemaInfo(
        id=str(uuid4()),
        database_id=database_id,
        name="public",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_table(schema_id: str) -> Table:
    return Table(
        id=str(uuid4()),
        schema_id=schema_id,
        name="users",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_column(table_id: str) -> Column:
    return Column(
        id=str(uuid4()),
        table_id=table_id,
        name="id",
        ordinal_position=1,
        data_type="integer",
        is_nullable=False,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_rel() -> Relationship:
    return Relationship(
        id=str(uuid4()),
        tenant_id=str(uuid4()),
        source_table_id=str(uuid4()),
        source_column="id",
        target_table_id=str(uuid4()),
        target_column="user_id",
        created_at=_NOW,
    )


def _build_mock_repo(repo_class, list_return, get_return=None, extra_methods: dict | None = None):
    repo = MagicMock(spec=repo_class)
    repo.list = AsyncMock(return_value=list_return)
    repo.get = AsyncMock(return_value=get_return)
    if extra_methods:
        for name, ret in extra_methods.items():
            setattr(repo, name, AsyncMock(return_value=ret))
    return repo


def _build_app(
    mock_tenant_repo,
    mock_db_repo,
    mock_schema_repo,
    mock_table_repo,
    mock_column_repo,
    mock_rel_repo,
    mock_qdrant,
    mock_sync_service=None,
):
    app = create_ke_api()
    mock_session = MagicMock()
    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_qdrant] = lambda: mock_qdrant
    app.dependency_overrides[_get_tenant_repo] = lambda: mock_tenant_repo
    app.dependency_overrides[_get_db_repo] = lambda: mock_db_repo
    app.dependency_overrides[_get_schema_repo] = lambda: mock_schema_repo
    app.dependency_overrides[_get_table_repo] = lambda: mock_table_repo
    app.dependency_overrides[_get_column_repo] = lambda: mock_column_repo
    app.dependency_overrides[_get_rel_repo] = lambda: mock_rel_repo
    app.dependency_overrides[_get_vector_repo] = lambda: VectorRepository(mock_qdrant)
    if mock_sync_service is not None:
        app.dependency_overrides[_get_metadata_sync_service] = lambda: mock_sync_service
    return app


@pytest_asyncio.fixture
async def async_ke_client() -> AsyncGenerator[AsyncClient, None]:
    app = create_ke_api()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def async_ke_client_auth() -> AsyncGenerator[AsyncClient, None]:
    tenant = _make_tenant()
    tenant_repo = _build_mock_repo(
        TenantRepository,
        list_return=([tenant], 1),
        get_return=tenant,
        extra_methods={"get_by_slug": tenant},
    )
    db = _make_db(tenant_id=tenant.id)
    db_repo = _build_mock_repo(DatabaseConfigRepository, list_return=([db], 1), get_return=db)
    schema = _make_schema_info(database_id=db.id)
    schema_repo = _build_mock_repo(
        SchemaInfoRepository, list_return=([schema], 1), get_return=schema
    )
    table = _make_table(schema_id=schema.id)
    table_repo = _build_mock_repo(TableRepository, list_return=([table], 1), get_return=table)
    col = _make_column(table_id=table.id)
    col_repo = _build_mock_repo(ColumnRepository, list_return=([col], 1), get_return=col)
    rel = _make_rel()
    rel_repo = _build_mock_repo(RelationshipRepository, list_return=([rel], 1), get_return=rel)
    mock_qdrant = MagicMock(spec=AsyncQdrantClient)

    app = _build_app(tenant_repo, db_repo, schema_repo, table_repo, col_repo, rel_repo, mock_qdrant)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Service-Token": "ke_dev_token_2026"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def async_ke_client_not_found() -> AsyncGenerator[AsyncClient, None]:
    tenant_repo = _build_mock_repo(
        TenantRepository, list_return=([], 0), get_return=None, extra_methods={"get_by_slug": None}
    )
    db_repo = _build_mock_repo(DatabaseConfigRepository, list_return=([], 0), get_return=None)
    schema_repo = _build_mock_repo(SchemaInfoRepository, list_return=([], 0), get_return=None)
    table_repo = _build_mock_repo(TableRepository, list_return=([], 0), get_return=None)
    col_repo = _build_mock_repo(ColumnRepository, list_return=([], 0), get_return=None)
    rel_repo = _build_mock_repo(RelationshipRepository, list_return=([], 0), get_return=None)
    mock_qdrant = MagicMock(spec=AsyncQdrantClient)

    app = _build_app(tenant_repo, db_repo, schema_repo, table_repo, col_repo, rel_repo, mock_qdrant)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Service-Token": "ke_dev_token_2026"},
    ) as client:
        yield client
