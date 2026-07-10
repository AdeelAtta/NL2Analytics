from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ke.models.schema import (
    SchemaChange,
    SchemaChangeType,
)
from ke.models.schema import (
    SchemaVersion as SchemaVersionModel,
)
from ke.stores.schema.versioning import (
    SchemaVersionOrm,
    VersioningService,
    _classify_change,
    _compute_ddl_hash,
)


def test_compute_ddl_hash_normalizes_whitespace() -> None:
    h1 = _compute_ddl_hash("CREATE TABLE foo (id INT)")
    h2 = _compute_ddl_hash("  CREATE   TABLE foo (id INT)  ")
    assert h1 == h2


def test_compute_ddl_hash_differs_for_different_ddl() -> None:
    h1 = _compute_ddl_hash("CREATE TABLE foo (id INT)")
    h2 = _compute_ddl_hash("CREATE TABLE foo (id BIGINT)")
    assert h1 != h2


class TestClassifyChange:
    def test_initial_ddl_returns_table_added(self) -> None:
        changes = _classify_change(None, "CREATE TABLE foo (id INT)")
        assert len(changes) == 1
        assert changes[0]["change_type"] == "TABLE_ADDED"

    def test_identical_ddl_returns_fallback_change(self) -> None:
        ddl = "CREATE TABLE foo (id INT)"
        changes = _classify_change(ddl, ddl)
        assert len(changes) == 1
        assert changes[0]["change_type"] == "COLUMN_TYPE_CHANGED"

    def test_parse_error_returns_fallback_change(self) -> None:
        changes = _classify_change("invalid sql {{", "CREATE TABLE foo (id INT)")
        assert len(changes) >= 1

    def test_column_type_change(self) -> None:
        old = "CREATE TABLE foo (id INT)"
        new = "CREATE TABLE foo (id BIGINT)"
        changes = _classify_change(old, new)
        assert len(changes) >= 1


class TestSchemaVersionOrm:
    def test_orm_has_expected_columns(self) -> None:
        columns = {c.name for c in SchemaVersionOrm.__table__.columns}
        expected = {
            "id", "schema_id", "version", "changes", "ddl_snapshot",
            "triggered_by", "created_at",
        }
        assert expected.issubset(columns)

    def test_orm_schema(self) -> None:
        assert SchemaVersionOrm.__table_args__["schema"] == "schema_store"


class TestVersioningService:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        session = AsyncMock()
        session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        )
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    async def test_detect_changes_first_version(self, mock_session: AsyncMock) -> None:
        service = VersioningService(mock_session)
        version = await service.detect_changes(
            schema_id="sc-1", new_ddl="CREATE TABLE foo (id INT)", triggered_by="manual"
        )
        assert version.version == 1
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_detect_changes_increments_version(self, mock_session: AsyncMock) -> None:
        existing = MagicMock()
        existing.scalar_one_or_none.return_value = 2
        mock_session.execute.return_value = existing

        service = VersioningService(mock_session)
        version = await service.detect_changes(
            schema_id="sc-1", new_ddl="CREATE TABLE foo (id INT)", triggered_by="connector"
        )
        assert version.version == 3

    async def test_get_version_history_empty(self, mock_session: AsyncMock) -> None:
        service = VersioningService(mock_session)
        history = await service.get_version_history("sc-1")
        assert history == []

    async def test_get_version_returns_none_for_missing(self, mock_session: AsyncMock) -> None:
        service = VersioningService(mock_session)
        result = await service.get_version("sc-1", 99)
        assert result is None

    async def test_get_version_returns_version_when_found(self, mock_session: AsyncMock) -> None:
        now = datetime.now(UTC)
        mock_orm = MagicMock()
        mock_orm.id = "sv-1"
        mock_orm.schema_id = "sc-1"
        mock_orm.version = 1
        mock_orm.changes = [{"change_type": "TABLE_ADDED", "object_name": "schema", "details": {}}]
        mock_orm.ddl_snapshot = "CREATE TABLE foo (id INT)"
        mock_orm.triggered_by = "connector"
        mock_orm.created_at = now

        mock_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_orm)
        )

        service = VersioningService(mock_session)
        result = await service.get_version("sc-1", 1)
        assert result is not None
        assert result.version == 1
        assert result.schema_id == "sc-1"


class TestSchemaChangeType:
    def test_all_types_have_expected_values(self) -> None:
        assert SchemaChangeType.TABLE_ADDED.value == "TABLE_ADDED"
        assert SchemaChangeType.TABLE_DROPPED.value == "TABLE_DROPPED"
        assert SchemaChangeType.COLUMN_ADDED.value == "COLUMN_ADDED"
        assert SchemaChangeType.COLUMN_DROPPED.value == "COLUMN_DROPPED"
        assert SchemaChangeType.COLUMN_RENAMED.value == "COLUMN_RENAMED"
        assert SchemaChangeType.COLUMN_TYPE_CHANGED.value == "COLUMN_TYPE_CHANGED"
        assert SchemaChangeType.COLUMN_NULLABLE_CHANGED.value == "COLUMN_NULLABLE_CHANGED"
        assert SchemaChangeType.RELATIONSHIP_ADDED.value == "RELATIONSHIP_ADDED"
        assert SchemaChangeType.RELATIONSHIP_DROPPED.value == "RELATIONSHIP_DROPPED"

    def test_schema_change_has_required_fields(self) -> None:
        change = SchemaChange(change_type=SchemaChangeType.COLUMN_ADDED, object_name="age")
        assert change.change_type == SchemaChangeType.COLUMN_ADDED
        assert change.object_name == "age"
        assert change.details == {}

    def test_schema_change_with_details(self) -> None:
        change = SchemaChange(
            change_type=SchemaChangeType.COLUMN_TYPE_CHANGED,
            object_name="id",
            details={"old_type": "INT", "new_type": "BIGINT"},
        )
        assert change.details["old_type"] == "INT"
        assert change.details["new_type"] == "BIGINT"


class TestSchemaVersionModel:
    def test_valid_schema_version(self) -> None:
        now = datetime.now(UTC)
        version = SchemaVersionModel(
            id="sv-1",
            schema_id="sc-1",
            version=1,
            changes=[],
            ddl_snapshot="CREATE TABLE foo (id INT)",
            triggered_by="connector",
            created_at=now,
        )
        assert version.id == "sv-1"
        assert version.schema_id == "sc-1"
        assert version.version == 1

    def test_default_triggered_by(self) -> None:
        now = datetime.now(UTC)
        version = SchemaVersionModel(
            id="sv-1",
            schema_id="sc-1",
            version=1,
            created_at=now,
        )
        assert version.triggered_by == "connector"
