from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ke.api.main import create_ke_api
from ke.api.routes.query import _get_query_service
from ke.models.schema import Column, Table
from ke.models.vector import SearchResult, VectorPayload
from ke.services.query import DDLRenderer, QueryService, _parse_vector_results
from ke.stores.vector.repository import VectorRepository

_NOW = datetime.now(UTC)


def _make_table(id: str = "t1", name: str = "users", schema_id: str = "s1", description: str | None = "User accounts") -> Table:
    return Table(
        id=id,
        schema_id=schema_id,
        name=name,
        description=description,
        row_estimate=0,
        version=1,
        is_active=True,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_column(
    id: str = "c1",
    table_id: str = "t1",
    name: str = "id",
    data_type: str = "integer",
    ordinal_position: int = 1,
    is_nullable: bool = False,
    is_primary_key: bool = True,
    is_unique: bool = False,
    default_value: str | None = None,
    foreign_key_table: str | None = None,
    foreign_key_column: str | None = None,
    description: str | None = None,
) -> Column:
    return Column(
        id=id,
        table_id=table_id,
        name=name,
        ordinal_position=ordinal_position,
        data_type=data_type,
        is_nullable=is_nullable,
        is_primary_key=is_primary_key,
        is_unique=is_unique,
        default_value=default_value,
        foreign_key_table=foreign_key_table,
        foreign_key_column=foreign_key_column,
        description=description,
        created_at=_NOW,
        updated_at=_NOW,
    )


class TestDDLRenderer:
    def test_render_table_basic(self):
        table = _make_table()
        columns = [
            _make_column(name="id", data_type="integer", is_primary_key=True),
            _make_column(id="c2", name="email", data_type="varchar(255)", is_primary_key=False),
        ]
        ddl = DDLRenderer.render_table(table, columns)
        assert "CREATE TABLE users" in ddl
        assert "id INTEGER" in ddl
        assert "email VARCHAR(255)" in ddl
        assert "PRIMARY KEY (id)" in ddl

    def test_render_table_with_fk(self):
        table = _make_table(name="orders")
        columns = [
            _make_column(id="c1", name="id", data_type="integer", is_primary_key=True),
            _make_column(
                id="c2",
                name="user_id",
                data_type="integer",
                is_primary_key=False,
                foreign_key_table="users",
                foreign_key_column="id",
            ),
        ]
        ddl = DDLRenderer.render_table(table, columns)
        assert "FOREIGN KEY (user_id) REFERENCES users(id)" in ddl

    def test_render_table_with_not_null(self):
        table = _make_table()
        columns = [
            _make_column(name="id", is_primary_key=True),
            _make_column(id="c2", name="email", data_type="text", is_nullable=True),
        ]
        ddl = DDLRenderer.render_table(table, columns)
        assert "id INTEGER NOT NULL" in ddl
        assert "email TEXT" in ddl
        assert "NOT NULL" not in ddl.split("email TEXT")[1] if "email TEXT" in ddl else True

    def test_render_table_with_default(self):
        table = _make_table()
        columns = [
            _make_column(id="c1", name="status", data_type="text", default_value="'active'"),
        ]
        ddl = DDLRenderer.render_table(table, columns)
        assert "DEFAULT 'active'" in ddl

    def test_render_table_with_description(self):
        table = _make_table(description="Stores user information")
        ddl = DDLRenderer.render_table(table, [])
        assert "-- Stores user information" in ddl

    def test_render_table_type_mapping(self):
        table = _make_table()
        columns = [
            _make_column(id="c1", name="a", data_type="bigint"),
            _make_column(id="c2", name="b", data_type="boolean"),
            _make_column(id="c3", name="c", data_type="timestamp"),
            _make_column(id="c4", name="d", data_type="numeric(10,2)"),
            _make_column(id="c5", name="e", data_type="jsonb"),
        ]
        ddl = DDLRenderer.render_table(table, columns)
        assert "a BIGINT" in ddl
        assert "b BOOLEAN" in ddl
        assert "c TIMESTAMP" in ddl
        assert "d NUMERIC(10,2)" in ddl
        assert "e JSONB" in ddl

    def test_render_table_unknown_type(self):
        table = _make_table()
        columns = [_make_column(id="c1", name="f", data_type="custom_type")]
        ddl = DDLRenderer.render_table(table, columns)
        assert "f CUSTOM_TYPE" in ddl

    def test_render_tables_multiple(self):
        t1 = _make_table(id="t1", name="users")
        t2 = _make_table(id="t2", name="orders", schema_id="s1")
        result = DDLRenderer.render_tables([
            (t1, [_make_column(name="id")]),
            (t2, [_make_column(id="c2", name="total", data_type="numeric")]),
        ])
        assert "users" in result
        assert "orders" in result
        assert "CREATE TABLE users" in result["users"]
        assert "CREATE TABLE orders" in result["orders"]


class TestQueryService:
    @pytest.fixture
    def mock_vector_repo(self):
        repo = MagicMock(spec=VectorRepository)
        repo.search_hybrid = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def mock_table_repo(self):
        repo = MagicMock(spec=VectorRepository)
        repo.list = AsyncMock(return_value=([], 0))
        repo.get = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def mock_column_repo(self):
        repo = MagicMock(spec=VectorRepository)
        repo.list_by_table = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def service(self, mock_vector_repo):
        return QueryService(
            vector_repo=mock_vector_repo,
            table_repo=None,
            column_repo=None,
        )

    async def test_search_context_no_results(self, service, mock_vector_repo):
        mock_vector_repo.search_hybrid.return_value = []
        result = await service.search_context("find users", "tenant1")
        assert result["total_results"] == 0
        assert result["tables"] == []
        assert result["columns"] == []

    async def test_search_context_with_results(self, service, mock_vector_repo):
        mock_vector_repo.search_hybrid.return_value = [
            SearchResult(
                id="tenant1:table:users",
                score=0.95,
                payload=VectorPayload(
                    tenant_id="tenant1",
                    content_type="schema_element",
                    source_id="schema/users",
                    text="Table users: User accounts",
                    metadata={},
                    created_at=_NOW,
                ),
            ),
        ]
        result = await service.search_context("find users", "tenant1")
        assert result["total_results"] == 1
        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "users"

    async def test_get_table_context_not_found(self, service):
        result = await service.get_table_context("nonexistent")
        assert result is None

    async def test_get_table_context_no_repos(self, service):
        result = await service.get_table_context("t1")
        assert result is None

    async def test_render_ddl_no_repos(self, service):
        result = await service.render_ddl(["t1"])
        assert result == {}


class TestParseVectorResults:
    def test_parse_tables(self):
        results = [
            SearchResult(
                id="t1:table:users",
                score=0.9,
                payload=VectorPayload(
                    tenant_id="t1",
                    content_type="schema_element",
                    source_id="schema/users",
                    text="Table users",
                    metadata={},
                    created_at=_NOW,
                ),
            ),
            SearchResult(
                id="t1:table:orders",
                score=0.8,
                payload=VectorPayload(
                    tenant_id="t1",
                    content_type="schema_element",
                    source_id="schema/orders",
                    text="Table orders",
                    metadata={},
                    created_at=_NOW,
                ),
            ),
        ]
        parsed = _parse_vector_results(results, "t1")
        assert len(parsed["tables"]) == 2
        assert parsed["tables"][0]["name"] == "users"
        assert parsed["tables"][1]["name"] == "orders"

    def test_parse_columns(self):
        results = [
            SearchResult(
                id="t1:column:users.id",
                score=0.85,
                payload=VectorPayload(
                    tenant_id="t1",
                    content_type="schema_element",
                    source_id="schema/users/id",
                    text="Column users.id (integer): Primary key",
                    metadata={},
                    created_at=_NOW,
                ),
            ),
        ]
        parsed = _parse_vector_results(results, "t1")
        assert len(parsed["columns"]) == 1
        assert parsed["columns"][0]["name"] == "users.id"
        assert parsed["columns"][0]["table"] == "users"

    def test_parse_relationships(self):
        results = [
            SearchResult(
                id="t1:rel:orders.user_id->users.id",
                score=0.75,
                payload=VectorPayload(
                    tenant_id="t1",
                    content_type="schema_element",
                    source_id="schema/orders/user_id->users",
                    text="Relationship: orders.user_id -> users.id",
                    metadata={},
                    created_at=_NOW,
                ),
            ),
        ]
        parsed = _parse_vector_results(results, "t1")
        assert len(parsed["relationships"]) == 1
        assert parsed["relationships"][0]["key"] == "orders.user_id->users.id"

    def test_parse_deduplicates(self):
        results = [
            SearchResult(
                id="t1:table:users",
                score=0.9,
                payload=VectorPayload(
                    tenant_id="t1",
                    content_type="schema_element",
                    source_id="schema/users",
                    text="Table users",
                    metadata={},
                    created_at=_NOW,
                ),
            ),
            SearchResult(
                id="t1:table:users",
                score=0.7,
                payload=VectorPayload(
                    tenant_id="t1",
                    content_type="schema_element",
                    source_id="schema/users",
                    text="Table users (lower score)",
                    metadata={},
                    created_at=_NOW,
                ),
            ),
        ]
        parsed = _parse_vector_results(results, "t1")
        assert len(parsed["tables"]) == 1


class TestQueryRoutes:
    @pytest.fixture
    def client(self):
        app = create_ke_api()
        mock_service = MagicMock(spec=QueryService)
        mock_service.search_context = AsyncMock(return_value={
            "question": "test",
            "tenant_id": "default",
            "total_results": 0,
            "tables": [],
            "columns": [],
            "relationships": [],
            "ddl_context": "",
            "results": [],
        })
        mock_service.get_table_context = AsyncMock(return_value={
            "id": "t1",
            "name": "users",
            "columns": [],
            "ddl": "CREATE TABLE users ();",
        })
        mock_service.render_ddl = AsyncMock(return_value={"users": "CREATE TABLE users ();"})
        app.dependency_overrides[_get_query_service] = lambda: mock_service
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        return AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-Service-Token": "ke_dev_token_2026"},
        )

    async def test_search_context_success(self, client):
        async with client as ac:
            resp = await ac.post(
                "/v1/ke/query/context",
                json={"question": "find users", "limit": 5},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    async def test_get_table_context_success(self, client):
        async with client as ac:
            resp = await ac.get("/v1/ke/query/context/table/t1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["ddl"] == "CREATE TABLE users ();"

    async def test_render_ddl_success(self, client):
        async with client as ac:
            resp = await ac.post(
                "/v1/ke/query/render-ddl",
                json={"table_ids": ["t1"]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "users" in body["data"]["ddl"]

    async def test_search_context_missing_question(self, client):
        async with client as ac:
            resp = await ac.post("/v1/ke/query/context", json={})
        assert resp.status_code == 422
