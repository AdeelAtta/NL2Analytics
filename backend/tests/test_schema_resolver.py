from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ke.models.planning import QueryIntent, QueryType, TableRef
from ke.services.schema_resolver import SchemaResolver


@pytest.fixture
def mock_table_repo() -> MagicMock:
    mock = MagicMock()
    mock.list = AsyncMock()
    return mock


@pytest.fixture
def mock_column_repo() -> MagicMock:
    mock = MagicMock()
    mock.list_by_table = AsyncMock()
    return mock


@pytest.fixture
def mock_rel_repo() -> MagicMock:
    mock = MagicMock()
    mock.list_by_source_table = AsyncMock()
    mock.list_by_target_table = AsyncMock()
    return mock


def _make_table(id: str, name: str, description: str = ""):
    tbl = MagicMock()
    tbl.id = id
    tbl.name = name
    tbl.description = description
    tbl.schema_name = ""
    tbl.row_estimate = 100
    return tbl


def _make_column(table_id: str, name: str, data_type: str = "text", is_pk: bool = False):
    col = MagicMock()
    col.table_id = table_id
    col.name = name
    col.data_type = data_type
    col.is_nullable = True
    col.is_primary_key = is_pk
    col.ordinal_position = 1
    return col


class TestSchemaResolver:
    @pytest.mark.asyncio
    async def test_resolve_empty_intent_tables(self, mock_table_repo, mock_column_repo, mock_rel_repo) -> None:
        resolver = SchemaResolver(table_repo=mock_table_repo, column_repo=mock_column_repo, rel_repo=mock_rel_repo)
        intent = QueryIntent(query_type=QueryType.SIMPLE_SELECT, tables=[])

        result = await resolver.resolve(intent)

        assert result["tables"] == []
        assert result["columns"] == []
        assert result["relationships"] == []
        assert result["ddl_context"] == ""

    @pytest.mark.asyncio
    async def test_resolve_no_repos_fallback(self) -> None:
        resolver = SchemaResolver()
        intent = QueryIntent(query_type=QueryType.SIMPLE_SELECT, tables=[TableRef(id="", name="users")])

        result = await resolver.resolve(intent)

        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "users"

    @pytest.mark.asyncio
    async def test_resolve_finds_tables_and_columns(self, mock_table_repo, mock_column_repo, mock_rel_repo) -> None:
        users_tbl = _make_table("t1", "users")
        orders_tbl = _make_table("t2", "orders")
        mock_table_repo.list.side_effect = [
            ([users_tbl], 1),
            ([orders_tbl], 1),
        ]
        mock_column_repo.list_by_table.side_effect = [
            [_make_column("t1", "id", "integer", True), _make_column("t1", "name", "text")],
            [_make_column("t2", "id", "integer", True), _make_column("t2", "user_id", "integer"), _make_column("t2", "total", "decimal")],
        ]
        mock_rel_repo.list_by_source_table.return_value = []
        mock_rel_repo.list_by_target_table.return_value = []

        resolver = SchemaResolver(table_repo=mock_table_repo, column_repo=mock_column_repo, rel_repo=mock_rel_repo)
        intent = QueryIntent(query_type=QueryType.JOIN, tables=[TableRef(id="", name="users"), TableRef(id="", name="orders")])

        result = await resolver.resolve(intent)

        assert len(result["tables"]) == 2
        assert result["tables"][0]["name"] == "users"
        assert result["tables"][1]["name"] == "orders"

        assert len(result["columns"]) == 5
        assert result["ddl_context"] != ""

    @pytest.mark.asyncio
    async def test_resolve_ddl_context_contains_table_names(self, mock_table_repo, mock_column_repo, mock_rel_repo) -> None:
        users_tbl = _make_table("t1", "users")
        mock_table_repo.list.return_value = ([users_tbl], 1)
        mock_column_repo.list_by_table.return_value = [
            _make_column("t1", "id", "integer", True),
            _make_column("t1", "email", "text"),
        ]
        mock_rel_repo.list_by_source_table.return_value = []
        mock_rel_repo.list_by_target_table.return_value = []

        resolver = SchemaResolver(table_repo=mock_table_repo, column_repo=mock_column_repo, rel_repo=mock_rel_repo)
        intent = QueryIntent(query_type=QueryType.SIMPLE_SELECT, tables=[TableRef(id="", name="users")])

        result = await resolver.resolve(intent)

        assert "CREATE TABLE users" in result["ddl_context"]
        assert "id integer" in result["ddl_context"]
        assert "PK" in result["ddl_context"]
        assert "email text" in result["ddl_context"]

    @pytest.mark.asyncio
    async def test_resolve_relationships_in_ddl(self, mock_table_repo, mock_column_repo, mock_rel_repo) -> None:
        mock_table_repo.list.side_effect = [
            ([_make_table("t1", "users")], 1),
            ([_make_table("t2", "orders")], 1),
        ]
        mock_column_repo.list_by_table.return_value = [_make_column("t1", "id", "integer")]
        mock_column_repo.list_by_table.return_value = [_make_column("t2", "user_id", "integer")]

        rel = MagicMock()
        rel.source_table_id = "t1"
        rel.source_table_name = "users"
        rel.source_column = "id"
        rel.target_table_id = "t2"
        rel.target_table_name = "orders"
        rel.target_column = "user_id"
        rel.relationship_type = "foreign_key"
        mock_rel_repo.list_by_source_table.return_value = [rel]
        mock_rel_repo.list_by_target_table.return_value = []

        resolver = SchemaResolver(table_repo=mock_table_repo, column_repo=mock_column_repo, rel_repo=mock_rel_repo)
        intent = QueryIntent(query_type=QueryType.JOIN, tables=[TableRef(id="", name="users"), TableRef(id="", name="orders")])

        result = await resolver.resolve(intent)

        assert len(result["relationships"]) >= 1
        assert any("users" in r["source_table"] for r in result["relationships"])

    @pytest.mark.asyncio
    async def test_resolve_skips_duplicate_tables(self, mock_table_repo, mock_column_repo, mock_rel_repo) -> None:
        mock_table_repo.list.return_value = ([_make_table("t1", "users")], 1)
        mock_column_repo.list_by_table.return_value = []
        mock_rel_repo.list_by_source_table.return_value = []
        mock_rel_repo.list_by_target_table.return_value = []

        resolver = SchemaResolver(table_repo=mock_table_repo, column_repo=mock_column_repo, rel_repo=mock_rel_repo)
        intent = QueryIntent(query_type=QueryType.SIMPLE_SELECT, tables=[TableRef(id="", name="users"), TableRef(id="", name="users")])

        result = await resolver.resolve(intent)

        assert len(result["tables"]) == 1

    @pytest.mark.asyncio
    async def test_resolve_table_not_found_returns_unknown_entry(self, mock_table_repo, mock_column_repo, mock_rel_repo) -> None:
        mock_table_repo.list.return_value = ([], 0)

        resolver = SchemaResolver(table_repo=mock_table_repo, column_repo=mock_column_repo, rel_repo=mock_rel_repo)
        intent = QueryIntent(query_type=QueryType.SIMPLE_SELECT, tables=[TableRef(id="", name="nonexistent")])

        result = await resolver.resolve(intent)

        assert len(result["tables"]) == 1
        assert result["tables"][0]["id"] == ""
        assert result["tables"][0]["name"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_resolve_column_exception_returns_empty(self, mock_table_repo, mock_column_repo, mock_rel_repo) -> None:
        mock_table_repo.list.return_value = ([_make_table("t1", "users")], 1)
        mock_column_repo.list_by_table.side_effect = Exception("DB error")

        resolver = SchemaResolver(table_repo=mock_table_repo, column_repo=mock_column_repo)
        intent = QueryIntent(query_type=QueryType.SIMPLE_SELECT, tables=[TableRef(id="", name="users")])

        result = await resolver.resolve(intent)

        assert len(result["tables"]) == 1
        assert result["columns"] == []


