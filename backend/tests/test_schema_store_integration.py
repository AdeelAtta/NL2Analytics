from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ke.models.schema import (
    Column as ColumnModel,
    DatabaseConfig as DatabaseConfigModel,
    Relationship as RelationshipModel,
    SchemaInfo as SchemaInfoModel,
    Table as TableModel,
    Tenant as TenantModel,
)
from ke.stores.schema.repository import (
    ColumnRepository,
    DatabaseConfigRepository,
    RelationshipRepository,
    SchemaInfoRepository,
    TableRepository,
    TenantRepository,
)
from shared.models.pagination import PaginationParams

DSN = "postgresql+asyncpg://schemaintern:schemaintern_dev@localhost:5432/schemaintern"


@pytest_asyncio.fixture
async def pg_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(DSN, poolclass=NullPool)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


def _now() -> datetime:
    return datetime.now(UTC)


def _tid() -> str:
    return str(uuid.uuid4())


class TestTenantRepositoryPG:
    async def test_create_and_get(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        tenant_id = _tid()
        now = _now()
        tenant = TenantModel(id=tenant_id, name="Test Tenant", slug="test-tenant", created_at=now, updated_at=now)
        created = await repo.create(tenant)
        assert created.id == tenant_id
        assert created.name == "Test Tenant"
        assert created.slug == "test-tenant"
        assert created.tier == "starter"

        fetched = await repo.get(tenant_id)
        assert fetched is not None
        assert fetched.name == "Test Tenant"

    async def test_get_missing_returns_none(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        result = await repo.get(_tid())
        assert result is None

    async def test_update(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        tenant_id = _tid()
        now = _now()
        tenant = TenantModel(id=tenant_id, name="Original", slug="original", created_at=now, updated_at=now)
        await repo.create(tenant)

        updated = await repo.update(tenant_id, {"name": "Updated Name"})
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.slug == "original"

    async def test_update_missing_returns_none(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        result = await repo.update(_tid(), {"name": "Nope"})
        assert result is None

    async def test_soft_delete(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        tenant_id = _tid()
        now = _now()
        tenant = TenantModel(id=tenant_id, name="Delete Me", slug="delete-me", created_at=now, updated_at=now)
        await repo.create(tenant)

        deleted = await repo.delete(tenant_id)
        assert deleted is True

        fetched = await repo.get(tenant_id)
        assert fetched is None

    async def test_delete_missing_returns_false(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        result = await repo.delete(_tid())
        assert result is False

    async def test_list_returns_undeleted_only(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        now = _now()
        t1 = TenantModel(id=_tid(), name="A", slug="a", created_at=now, updated_at=now)
        t2 = TenantModel(id=_tid(), name="B", slug="b", created_at=now, updated_at=now)
        await repo.create(t1)
        await repo.create(t2)
        await repo.delete(t2.id)

        items, total = await repo.list()
        ids = {i.id for i in items}
        assert t1.id in ids
        assert t2.id not in ids

    async def test_get_by_slug(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        slug = "slug-test"
        tenant_id = _tid()
        now = _now()
        await repo.create(TenantModel(id=tenant_id, name="Slug Tenant", slug=slug, created_at=now, updated_at=now))

        found = await repo.get_by_slug(slug)
        assert found is not None
        assert found.id == tenant_id

        missing = await repo.get_by_slug("nonexistent")
        assert missing is None

    async def test_list_with_filters(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        now = _now()
        t1 = TenantModel(id=_tid(), name="Free", slug="free-t", tier="free", created_at=now, updated_at=now)
        t2 = TenantModel(id=_tid(), name="Pro", slug="pro-t", tier="pro", created_at=now, updated_at=now)
        t3 = TenantModel(id=_tid(), name="Enterprise", slug="ent-t", tier="enterprise", created_at=now, updated_at=now)
        for t in (t1, t2, t3):
            await repo.create(t)

        items, total = await repo.list(filters={"tier": "pro"})
        assert total == 1
        assert items[0].id == t2.id

    async def test_list_pagination(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        now = _now()
        ids = []
        for i in range(5):
            tid = _tid()
            ids.append(tid)
            await repo.create(TenantModel(id=tid, name=f"T{i}", slug=f"t{i}", created_at=now, updated_at=now))

        page1, total = await repo.list(pagination=PaginationParams(page=1, page_size=2))
        assert total >= 5
        assert len(page1) == 2

        page2, total = await repo.list(pagination=PaginationParams(page=2, page_size=2))
        assert len(page2) == 2

    async def test_hard_delete(self, pg_session: AsyncSession) -> None:
        repo = TenantRepository(pg_session)
        tenant_id = _tid()
        now = _now()
        await repo.create(TenantModel(id=tenant_id, name="Hard Delete", slug="hard-del", created_at=now, updated_at=now))

        deleted = await repo.delete(tenant_id, hard=True)
        assert deleted is True

        fetched = await repo.get(tenant_id)
        assert fetched is None


class TestDatabaseConfigRepositoryPG:
    async def test_create_and_list_by_tenant(self, pg_session: AsyncSession) -> None:
        tenant_repo = TenantRepository(pg_session)
        db_repo = DatabaseConfigRepository(pg_session)
        tenant_id = _tid()
        now = _now()
        await tenant_repo.create(TenantModel(id=tenant_id, name="T", slug="t", created_at=now, updated_at=now))

        db_id = _tid()
        db = DatabaseConfigModel(
            id=db_id, tenant_id=tenant_id, name="Test DB", db_type="postgresql",
            connection_hash="abc123", created_at=now, updated_at=now,
        )
        created = await db_repo.create(db)
        assert created.id == db_id
        assert created.db_type == "postgresql"

        items = await db_repo.list_by_tenant(tenant_id)
        assert len(items) == 1
        assert items[0].name == "Test DB"

    async def test_get(self, pg_session: AsyncSession) -> None:
        tenant_repo = TenantRepository(pg_session)
        db_repo = DatabaseConfigRepository(pg_session)
        tenant_id = _tid()
        now = _now()
        await tenant_repo.create(TenantModel(id=tenant_id, name="T", slug="t", created_at=now, updated_at=now))
        db_id = _tid()
        await db_repo.create(DatabaseConfigModel(
            id=db_id, tenant_id=tenant_id, name="DB", db_type="duckdb",
            connection_hash="def456", created_at=now, updated_at=now,
        ))

        fetched = await db_repo.get(db_id)
        assert fetched is not None
        assert fetched.db_type == "duckdb"

        missing = await db_repo.get(_tid())
        assert missing is None


class TestSchemaInfoRepositoryPG:
    async def test_full_hierarchy(self, pg_session: AsyncSession) -> None:
        tenant_repo = TenantRepository(pg_session)
        db_repo = DatabaseConfigRepository(pg_session)
        schema_repo = SchemaInfoRepository(pg_session)
        table_repo = TableRepository(pg_session)
        col_repo = ColumnRepository(pg_session)
        rel_repo = RelationshipRepository(pg_session)
        now = _now()

        tenant_id = _tid()
        await tenant_repo.create(TenantModel(id=tenant_id, name="Hierarchy", slug="hier", created_at=now, updated_at=now))
        db_id = _tid()
        await db_repo.create(DatabaseConfigModel(
            id=db_id, tenant_id=tenant_id, name="Hier DB", db_type="postgresql",
            connection_hash="h1", created_at=now, updated_at=now,
        ))
        schema_id = _tid()
        schema = await schema_repo.create(SchemaInfoModel(
            id=schema_id, database_id=db_id, name="public", created_at=now, updated_at=now,
        ))
        assert schema.name == "public"

        schemas = await schema_repo.list_by_database(db_id)
        assert len(schemas) == 1

        table_id = _tid()
        table = await table_repo.create(TableModel(
            id=table_id, schema_id=schema_id, name="users", created_at=now, updated_at=now,
        ))
        assert table.name == "users"

        tables = await table_repo.list_by_schema(schema_id)
        assert len(tables) == 1

        col_id = _tid()
        col = await col_repo.create(ColumnModel(
            id=col_id, table_id=table_id, name="id", ordinal_position=1,
            data_type="integer", is_primary_key=True, created_at=now, updated_at=now,
        ))
        assert col.name == "id"
        assert col.is_primary_key is True

        cols = await col_repo.list_by_table(table_id)
        assert len(cols) == 1

        pks = await col_repo.list_primary_keys(table_id)
        assert len(pks) == 1
        assert pks[0].name == "id"

        rel_id = _tid()
        rel = await rel_repo.create(RelationshipModel(
            id=rel_id, tenant_id=tenant_id, source_table_id=table_id,
            source_column="id", target_table_id=table_id,
            target_column="id", created_at=now,
        ))
        assert rel.relationship_type == "foreign_key"

        rels = await rel_repo.list_by_tenant(tenant_id)
        assert len(rels) == 1

    async def test_database_soft_delete_cascades_to_list(
        self, pg_session: AsyncSession,
    ) -> None:
        tenant_repo = TenantRepository(pg_session)
        db_repo = DatabaseConfigRepository(pg_session)
        now = _now()

        tenant_id = _tid()
        await tenant_repo.create(TenantModel(id=tenant_id, name="C", slug="c", created_at=now, updated_at=now))
        db_id = _tid()
        await db_repo.create(DatabaseConfigModel(
            id=db_id, tenant_id=tenant_id, name="C DB", db_type="postgresql",
            connection_hash="ch", created_at=now, updated_at=now,
        ))

        await db_repo.delete(db_id)
        items = await db_repo.list_by_tenant(tenant_id)
        assert items == []


class TestColumnRepositoryPG:
    async def test_list_by_table_empty(self, pg_session: AsyncSession) -> None:
        col_repo = ColumnRepository(pg_session)
        items = await col_repo.list_by_table(_tid())
        assert items == []

    async def test_list_primary_keys_empty(self, pg_session: AsyncSession) -> None:
        col_repo = ColumnRepository(pg_session)
        items = await col_repo.list_primary_keys(_tid())
        assert items == []

    async def test_foreign_key_fields(self, pg_session: AsyncSession) -> None:
        tenant_repo = TenantRepository(pg_session)
        db_repo = DatabaseConfigRepository(pg_session)
        schema_repo = SchemaInfoRepository(pg_session)
        table_repo = TableRepository(pg_session)
        col_repo = ColumnRepository(pg_session)
        now = _now()

        tenant_id = _tid()
        await tenant_repo.create(TenantModel(id=tenant_id, name="FK", slug="fk", created_at=now, updated_at=now))
        db_id = _tid()
        await db_repo.create(DatabaseConfigModel(
            id=db_id, tenant_id=tenant_id, name="FK DB", db_type="postgresql",
            connection_hash="fk", created_at=now, updated_at=now,
        ))
        schema_id = _tid()
        await schema_repo.create(SchemaInfoModel(
            id=schema_id, database_id=db_id, name="public", created_at=now, updated_at=now,
        ))
        t1_id = _tid()
        await table_repo.create(TableModel(id=t1_id, schema_id=schema_id, name="orders", created_at=now, updated_at=now))
        t2_id = _tid()
        await table_repo.create(TableModel(id=t2_id, schema_id=schema_id, name="users", created_at=now, updated_at=now))

        col = await col_repo.create(ColumnModel(
            id=_tid(), table_id=t1_id, name="user_id", ordinal_position=1,
            data_type="integer", foreign_key_table="users", foreign_key_column="id",
            created_at=now, updated_at=now,
        ))
        assert col.foreign_key_table == "users"
        assert col.foreign_key_column == "id"

    async def test_nullable_default(self, pg_session: AsyncSession) -> None:
        tenant_repo = TenantRepository(pg_session)
        db_repo = DatabaseConfigRepository(pg_session)
        schema_repo = SchemaInfoRepository(pg_session)
        table_repo = TableRepository(pg_session)
        col_repo = ColumnRepository(pg_session)
        now = _now()

        tenant_id = _tid()
        await tenant_repo.create(TenantModel(id=tenant_id, name="N", slug="n", created_at=now, updated_at=now))
        db_id = _tid()
        await db_repo.create(DatabaseConfigModel(
            id=db_id, tenant_id=tenant_id, name="N DB", db_type="postgresql",
            connection_hash="n", created_at=now, updated_at=now,
        ))
        schema_id = _tid()
        await schema_repo.create(SchemaInfoModel(
            id=schema_id, database_id=db_id, name="public", created_at=now, updated_at=now,
        ))
        table_id = _tid()
        await table_repo.create(TableModel(id=table_id, schema_id=schema_id, name="t", created_at=now, updated_at=now))

        col = await col_repo.create(ColumnModel(
            id=_tid(), table_id=table_id, name="nullable_col", ordinal_position=1,
            data_type="text", created_at=now, updated_at=now,
        ))
        assert col.is_nullable is True
        assert col.is_primary_key is False
        assert col.is_unique is False


class TestRelationshipRepositoryPG:
    async def test_list_by_source_and_target(self, pg_session: AsyncSession) -> None:
        tenant_repo = TenantRepository(pg_session)
        db_repo = DatabaseConfigRepository(pg_session)
        schema_repo = SchemaInfoRepository(pg_session)
        table_repo = TableRepository(pg_session)
        rel_repo = RelationshipRepository(pg_session)
        now = _now()

        tenant_id = _tid()
        await tenant_repo.create(TenantModel(id=tenant_id, name="R", slug="r", created_at=now, updated_at=now))
        db_id = _tid()
        await db_repo.create(DatabaseConfigModel(
            id=db_id, tenant_id=tenant_id, name="R DB", db_type="postgresql",
            connection_hash="r", created_at=now, updated_at=now,
        ))
        schema_id = _tid()
        await schema_repo.create(SchemaInfoModel(
            id=schema_id, database_id=db_id, name="public", created_at=now, updated_at=now,
        ))
        src_id = _tid()
        tgt_id = _tid()
        await table_repo.create(TableModel(id=src_id, schema_id=schema_id, name="src", created_at=now, updated_at=now))
        await table_repo.create(TableModel(id=tgt_id, schema_id=schema_id, name="tgt", created_at=now, updated_at=now))

        rel_id = _tid()
        await rel_repo.create(RelationshipModel(
            id=rel_id, tenant_id=tenant_id, source_table_id=src_id,
            source_column="id", target_table_id=tgt_id,
            target_column="ref_id", created_at=now,
        ))

        by_src = await rel_repo.list_by_source_table(src_id)
        assert len(by_src) == 1
        assert by_src[0].target_column == "ref_id"

        by_tgt = await rel_repo.list_by_target_table(tgt_id)
        assert len(by_tgt) == 1

    async def test_inferred_relationship(self, pg_session: AsyncSession) -> None:
        tenant_repo = TenantRepository(pg_session)
        db_repo = DatabaseConfigRepository(pg_session)
        schema_repo = SchemaInfoRepository(pg_session)
        table_repo = TableRepository(pg_session)
        rel_repo = RelationshipRepository(pg_session)
        now = _now()

        tenant_id = _tid()
        await tenant_repo.create(TenantModel(id=tenant_id, name="I", slug="i", created_at=now, updated_at=now))
        db_id = _tid()
        await db_repo.create(DatabaseConfigModel(
            id=db_id, tenant_id=tenant_id, name="I DB", db_type="postgresql",
            connection_hash="i", created_at=now, updated_at=now,
        ))
        schema_id = _tid()
        await schema_repo.create(SchemaInfoModel(
            id=schema_id, database_id=db_id, name="public", created_at=now, updated_at=now,
        ))
        s_id = _tid()
        t_id = _tid()
        await table_repo.create(TableModel(id=s_id, schema_id=schema_id, name="s", created_at=now, updated_at=now))
        await table_repo.create(TableModel(id=t_id, schema_id=schema_id, name="t", created_at=now, updated_at=now))

        rel = await rel_repo.create(RelationshipModel(
            id=_tid(), tenant_id=tenant_id, source_table_id=s_id,
            source_column="a", target_table_id=t_id, target_column="b",
            relationship_type="inferred", confidence=0.85, discovered_by="inferer",
            created_at=now,
        ))
        assert rel.relationship_type == "inferred"
        assert rel.confidence == 0.85
        assert rel.discovered_by == "inferer"

    async def test_list_by_tenant_empty(self, pg_session: AsyncSession) -> None:
        rel_repo = RelationshipRepository(pg_session)
        items = await rel_repo.list_by_tenant(_tid())
        assert items == []
