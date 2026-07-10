from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ke.models.schema import Tenant as TenantModel
from ke.stores.schema.repository import (
    ColumnRepository,
    DatabaseConfigRepository,
    ORMBase,
    RelationshipRepository,
    SchemaInfoRepository,
    TableRepository,
    TenantOrm,
    TenantRepository,
)
from shared.models.pagination import PaginationParams


@pytest.fixture
def mock_result() -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    return result


@pytest.fixture
def mock_session(mock_result: MagicMock) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


class TestORMBase:
    def test_orm_base_importable(self) -> None:
        assert ORMBase is not None

    def test_tenant_orm_has_expected_columns(self) -> None:
        columns = {c.name for c in TenantOrm.__table__.columns}
        expected = {
            "id",
            "name",
            "slug",
            "tier",
            "status",
            "settings",
            "features",
            "created_at",
            "updated_at",
            "deleted_at",
        }
        assert expected.issubset(columns)

    def test_tenant_orm_schema(self) -> None:
        assert TenantOrm.__table_args__["schema"] == "public"


class TestTenantRepository:
    def test_instantiation(self, mock_session: AsyncMock) -> None:
        repo = TenantRepository(session=mock_session)
        assert repo._orm_class == TenantOrm

    def test_base_repository_has_crud_methods(self, mock_session: AsyncMock) -> None:
        repo = TenantRepository(session=mock_session)
        assert hasattr(repo, "create")
        assert hasattr(repo, "get")
        assert hasattr(repo, "update")
        assert hasattr(repo, "delete")
        assert hasattr(repo, "list")

    async def test_create_calls_session_methods(self, mock_session: AsyncMock) -> None:
        now = datetime.now(UTC)
        tenant = TenantModel(id="x", name="Acme", slug="acme", created_at=now, updated_at=now)
        repo = TenantRepository(session=mock_session)

        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = MagicMock(
            id="x", name="Acme", slug="acme", tier="starter", status="active",
            settings={}, features={}, created_at=now, updated_at=now, deleted_at=None,
        )
        mock_session.execute.return_value = mock_execute_result

        result = await repo.create(tenant)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()
        assert result.name == "Acme"

    async def test_get_returns_none_for_missing(self, mock_session: AsyncMock) -> None:
        repo = TenantRepository(session=mock_session)
        result = await repo.get("non-existent")
        assert result is None

    async def test_delete_returns_false_for_missing(self, mock_session: AsyncMock) -> None:
        repo = TenantRepository(session=mock_session)
        result = await repo.delete("non-existent")
        assert result is False

    async def test_get_returns_tenant_when_found(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        now = datetime.now(UTC)
        mock_orm = MagicMock()
        mock_orm.id = "tnt-1"
        mock_orm.name = "Acme"
        mock_orm.slug = "acme"
        mock_orm.tier = "starter"
        mock_orm.status = "active"
        mock_orm.settings = {}
        mock_orm.features = {}
        mock_orm.created_at = now
        mock_orm.updated_at = now
        mock_orm.deleted_at = None
        mock_result.scalar_one_or_none.return_value = mock_orm

        repo = TenantRepository(session=mock_session)
        result = await repo.get("tnt-1")
        assert result is not None
        assert result.name == "Acme"
        assert result.slug == "acme"


class TestSpecificRepositories:
    async def test_list_returns_empty(self, mock_session: AsyncMock) -> None:
        repo = DatabaseConfigRepository(session=mock_session)
        items = await repo.list_by_tenant("tnt-1")
        assert items == []

    async def test_schema_info_list(self, mock_session: AsyncMock) -> None:
        repo = SchemaInfoRepository(session=mock_session)
        items = await repo.list_by_database("db-1")
        assert items == []

    async def test_table_list(self, mock_session: AsyncMock) -> None:
        repo = TableRepository(session=mock_session)
        items = await repo.list_by_schema("si-1")
        assert items == []

    async def test_column_list(self, mock_session: AsyncMock) -> None:
        repo = ColumnRepository(session=mock_session)
        items = await repo.list_by_table("tbl-1")
        assert items == []

    async def test_relationship_list(self, mock_session: AsyncMock) -> None:
        repo = RelationshipRepository(session=mock_session)
        items = await repo.list_by_tenant("tnt-1")
        assert items == []


class TestPagination:
    def test_pagination_params_defaults(self) -> None:
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 50
        assert params.offset == 0

    async def test_list_respects_pagination(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        mock_result.scalar.return_value = 0
        repo = TenantRepository(session=mock_session)
        pagination = PaginationParams(page=2, page_size=10)
        items, total = await repo.list(pagination=pagination)
        assert items == []
        assert total == 0

    async def test_list_with_filters(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        mock_result.scalar.return_value = 0
        repo = TenantRepository(session=mock_session)
        items, total = await repo.list(filters={"tier": "enterprise"})
        assert items == []
        assert total == 0

    async def test_list_filters_deleted_at(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        mock_result.scalar.return_value = 0
        repo = TenantRepository(session=mock_session)
        items, total = await repo.list()
        assert items == []
        assert total == 0
